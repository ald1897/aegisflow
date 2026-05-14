from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from fastapi import status


class Permission(StrEnum):
    workflow_create = "workflow:create"
    workflow_review_decide = "workflow:review_decide"
    workflow_replay_create = "workflow:replay_create"
    workflow_replay_read = "workflow:replay_read"
    workflow_recovery_execute = "workflow:recovery_execute"
    events_outbox_retry = "events:outbox_retry"
    events_outbox_dead_letter = "events:outbox_dead_letter"
    workflow_projection_reconcile = "workflow:projection_reconcile"
    evaluation_run_create = "evaluation:run_create"
    evaluation_read = "evaluation:read"
    agent_execute = "agent:execute"
    tool_invoke = "tool:invoke"
    observability_read = "observability:read"
    policy_admin = "policy:admin"
    audit_read = "audit:read"


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    roles: tuple[str, ...]
    permissions: frozenset[Permission]


class LocalAuthorizationError(Exception):
    def __init__(self, *, error: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.status_code = status_code


LOCAL_ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "workflow_operator": frozenset({Permission.workflow_create}),
    "reviewer": frozenset({Permission.workflow_review_decide}),
    "compliance_analyst": frozenset(
        {
            Permission.workflow_replay_create,
            Permission.workflow_replay_read,
            Permission.evaluation_run_create,
            Permission.evaluation_read,
        }
    ),
    "recovery_operator": frozenset(
        {
            Permission.workflow_recovery_execute,
            Permission.events_outbox_retry,
            Permission.events_outbox_dead_letter,
            Permission.workflow_projection_reconcile,
        }
    ),
    "observability_reader": frozenset({Permission.observability_read}),
    "policy_admin": frozenset({Permission.policy_admin, Permission.audit_read}),
    "platform_admin": frozenset(Permission),
}


def parse_actor_context(actor_id: str | None, actor_roles: str | None, *, action_name: str) -> ActorContext:
    if actor_id is None or not actor_id.strip():
        raise LocalAuthorizationError(
            error="actor_required",
            message=f"{action_name} requires X-Actor-ID",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    roles = tuple(role.strip().lower() for role in (actor_roles or "").split(",") if role.strip())
    if not roles:
        raise LocalAuthorizationError(
            error="actor_roles_required",
            message=f"{action_name} requires X-Actor-Roles",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    permissions: set[Permission] = set()
    for role in roles:
        permissions.update(LOCAL_ROLE_PERMISSIONS.get(role, frozenset()))

    return ActorContext(actor_id=actor_id.strip(), roles=roles, permissions=frozenset(permissions))


def require_permissions(
    actor_id: str | None,
    actor_roles: str | None,
    required_permissions: Iterable[Permission],
    *,
    action_name: str,
) -> ActorContext:
    actor = parse_actor_context(actor_id, actor_roles, action_name=action_name)
    missing_permissions = [permission for permission in required_permissions if permission not in actor.permissions]
    if missing_permissions:
        permission_list = ", ".join(str(permission) for permission in missing_permissions)
        raise LocalAuthorizationError(
            error="actor_permission_denied",
            message=f"{action_name} requires permission {permission_list}",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return actor


def require_permission(
    actor_id: str | None,
    actor_roles: str | None,
    required_permission: Permission,
    *,
    action_name: str,
) -> ActorContext:
    return require_permissions(
        actor_id,
        actor_roles,
        (required_permission,),
        action_name=action_name,
    )
