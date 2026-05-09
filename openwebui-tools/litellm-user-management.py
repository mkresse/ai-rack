"""
title: LiteLLM User Management
author: martin
description: List and inspect LiteLLM users, list Open WebUI users, and sync Open WebUI users to LiteLLM.
version: 0.1.0
"""

from pydantic import BaseModel, Field
import httpx


async def emit_status(emitter, description: str, done: bool = False):
    await emitter({"type": "status", "data": {"description": description, "done": done}})


class Tools:
    def __init__(self):
        self.valves = self.Valves()

    class Valves(BaseModel):
        litellm_base_url: str = Field(
            "http://litellm:4000",
            description="Base URL of the LiteLLM instance",
        )

    class UserValves(BaseModel):
        api_key: str = Field("", description="LiteLLM API key")

    async def list_litellm_users(
        self,
        role: str = "",
        page: int = 1,
        page_size: int = 25,
        __user__: dict = {},
        __event_emitter__=None,
        __event_call__=None,
    ) -> str:
        """
        List internal users on the LiteLLM instance.
        Use this when the user wants to see who has access, check budgets, or look up LiteLLM users.

        :param role: Filter by role (proxy_admin, internal_user, internal_user_viewer). Leave empty for all.
        :param page: Page number (default 1).
        :param page_size: Users per page (default 25).
        :return: Formatted list of users with their details.
        """
        api_key = await self._get_api_key(__user__, __event_call__)
        client = LiteLlmClient(self.valves.litellm_base_url, api_key)

        await emit_status(__event_emitter__, "Fetching users from LiteLLM...")

        try:
            params = {"page": page, "page_size": page_size}
            if role:
                params["role"] = role
            data = await client.get("/user/list", params)
        except Exception as e:
            await emit_status(__event_emitter__, f"Error: {e}", done=True)
            raise

        users = data.get("users", [])

        await emit_status(__event_emitter__, f"Found {len(users)} users", done=True)

        lines = []
        for u in users:
            uid = u.get("user_id", "")
            email = u.get("user_email") or ""
            alias = u.get("user_alias") or ""
            urole = u.get("user_role") or ""
            spend = u.get("spend", 0)
            budget = u.get("max_budget")
            label = email or alias or uid
            budget_str = str(budget) if budget is not None else "unlimited"
            lines.append(
                f"- **{label}** | alias: {alias} | id: `{uid}` | role: {urole} | spend: ${spend:.4f} | budget: ${budget_str}"
            )
        return "\n".join(lines) if lines else "No users found."

    async def list_owui_users(
        self,
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        List all Open WebUI users.
        Use this when the user wants to see who has accounts in Open WebUI.

        :return: Formatted list of Open WebUI users.
        """
        if __user__.get("role") != "admin":
            return "Error: Only admins can list Open WebUI users."

        await emit_status(__event_emitter__, "Fetching Open WebUI users...")

        try:
            from open_webui.models.users import Users
            result = await Users.get_users()
        except Exception as e:
            await emit_status(__event_emitter__, f"Error: {e}", done=True)
            raise

        users = result["users"]

        await emit_status(__event_emitter__, f"Found {len(users)} users", done=True)

        lines = []
        for u in users:
            lines.append(f"- **{u.name}** | email: {u.email} | id: `{u.id}` | role: {u.role}")
        return "\n".join(lines) if lines else "No users found."

    async def sync_owui_users_to_litellm(
        self,
        __user__: dict = {},
        __event_emitter__=None,
        __event_call__=None,
    ) -> str:
        """
        Sync Open WebUI users to LiteLLM. Creates a LiteLLM user for each Open WebUI user
        that doesn't already exist, using the same user ID.
        Use this when the user wants to ensure all Open WebUI users have matching LiteLLM accounts.

        :return: Summary of created and skipped users.
        """
        if __user__.get("role") != "admin":
            return "Error: Only admins can sync users."

        api_key = await self._get_api_key(__user__, __event_call__)
        client = LiteLlmClient(self.valves.litellm_base_url, api_key)

        await emit_status(__event_emitter__, "Fetching Open WebUI users...")

        try:
            from open_webui.models.users import Users
            owui_users = (await Users.get_users())["users"]
        except Exception as e:
            await emit_status(__event_emitter__, f"Error fetching OWUI users: {e}", done=True)
            raise

        await emit_status(__event_emitter__, "Fetching existing LiteLLM users...")

        existing_ids = set()
        page = 1
        while True:
            data = await client.get("/user/list", {"page": page, "page_size": 100})
            for u in data.get("users", []):
                existing_ids.add(u.get("user_id"))
            if page >= data.get("total_pages", 1):
                break
            page += 1

        results = {"created": 0, "skipped": 0, "errors": []}
        for u in owui_users:
            if u.id in existing_ids:
                results["skipped"] += 1
                await emit_status(__event_emitter__, f"Skipping user {u.name}...")
                continue
            try:
                await client.post("/user/new", {
                    "user_id": u.id,
                    "user_email": u.email,
                    "user_alias": u.name,
                    "user_role": "internal_user_viewer",
                    "auto_create_key": False,
                })
                results["created"] += 1
                await emit_status(__event_emitter__, f"Created user {u.name}...")
            except Exception as e:
                results["errors"].append(f"{u.id}: {e}")

        await emit_status(
            __event_emitter__,
            f"{results['created']} created, {results['skipped']} skipped, {len(results['errors'])} errors",
            done=True,
        )

        summary = f"Created {results['created']} users, skipped {results['skipped']} (already exist)."
        if results["errors"]:
            summary += f"\n\nErrors ({len(results['errors'])}):\n" + "\n".join(f"- {e}" for e in results["errors"])

        return summary

    async def get_litellm_user(
        self,
        user_id: str,
        __user__: dict = {},
        __event_emitter__=None,
        __event_call__=None,
    ) -> str:
        """
        Get detailed information about a specific LiteLLM user, including their API keys.
        Use this when the user asks about a specific person's access, keys, or budget.

        :param user_id: The user ID (uuid) to look up.
        :return: JSON with user details and associated keys.
        """
        api_key = await self._get_api_key(__user__, __event_call__)
        client = LiteLlmClient(self.valves.litellm_base_url, api_key)

        await emit_status(__event_emitter__, f"Looking up user {user_id}...")

        try:
            data = await client.get("/v2/user/info", {"user_id": user_id})
        except Exception as e:
            await emit_status(__event_emitter__, f"Error: {e}", done=True)
            raise

        await emit_status(__event_emitter__, "Done", done=True)

        import json
        return json.dumps(data, indent=2, default=str)

    async def _get_api_key(self, __user__: dict, __event_call__=None) -> str:
        valves = __user__.get("valves")
        api_key = getattr(valves, "api_key", "") if valves else ""
        if api_key:
            return api_key
        if __event_call__:
            result = await __event_call__(
                {
                    "type": "input",
                    "data": {
                        "title": "LiteLLM API Key",
                        "message": "Enter your LiteLLM API key:",
                        "placeholder": "sk-...",
                        "type": "password",
                    },
                }
            )
            api_key = result
        if not api_key:
            raise ValueError(
                "No API key provided. Set it in User Valves or enter it when prompted."
            )
        return api_key


class LiteLlmClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"}

    async def get(self, path: str, params: dict = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}{path}",
                params=params,
                headers=self.headers,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

    async def post(self, path: str, json: dict = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}{path}",
                json=json,
                headers=self.headers,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
