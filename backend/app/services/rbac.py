"""Role-Based Access Control with team/organization support.

Provides organizations, teams, memberships, and fine-grained
permissions. Built on top of the existing auth system.
"""

import json
import logging
import os
import secrets
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("TRACES_DB_PATH", "traces.db")


# ── Permission Definitions ──────────────────────────────


class Permission:
    """Fine-grained permissions for RBAC."""
    # Trace permissions
    TRACE_READ = "trace:read"
    TRACE_WRITE = "trace:write"
    TRACE_DELETE = "trace:delete"

    # Dashboard permissions
    DASHBOARD_READ = "dashboard:read"
    DASHBOARD_WRITE = "dashboard:write"
    DASHBOARD_DELETE = "dashboard:delete"

    # Alert permissions
    ALERT_READ = "alert:read"
    ALERT_WRITE = "alert:write"
    ALERT_DELETE = "alert:delete"

    # Evaluation permissions
    EVALUATION_READ = "evaluation:read"
    EVALUATION_WRITE = "evaluation:write"
    EVALUATION_DELETE = "evaluation:delete"

    # Analytics permissions
    ANALYTICS_READ = "analytics:read"

    # Sampling permissions
    SAMPLING_READ = "sampling:read"
    SAMPLING_WRITE = "sampling:write"

    # Notification permissions
    NOTIFICATION_READ = "notification:read"
    NOTIFICATION_WRITE = "notification:write"

    # Retention permissions
    RETENTION_READ = "retention:read"
    RETENTION_WRITE = "retention:write"

    # Team management
    TEAM_READ = "team:read"
    TEAM_MANAGE = "team:manage"

    # Org management
    ORG_READ = "org:read"
    ORG_MANAGE = "org:manage"


class Role:
    """Predefined roles with permission sets."""
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

    PERMISSIONS = {
        OWNER: "all",  # All permissions
        ADMIN: [
            Permission.TRACE_READ, Permission.TRACE_WRITE, Permission.TRACE_DELETE,
            Permission.DASHBOARD_READ, Permission.DASHBOARD_WRITE, Permission.DASHBOARD_DELETE,
            Permission.ALERT_READ, Permission.ALERT_WRITE, Permission.ALERT_DELETE,
            Permission.EVALUATION_READ, Permission.EVALUATION_WRITE, Permission.EVALUATION_DELETE,
            Permission.ANALYTICS_READ,
            Permission.SAMPLING_READ, Permission.SAMPLING_WRITE,
            Permission.NOTIFICATION_READ, Permission.NOTIFICATION_WRITE,
            Permission.RETENTION_READ, Permission.RETENTION_WRITE,
            Permission.TEAM_READ, Permission.TEAM_MANAGE,
            Permission.ORG_READ,
        ],
        EDITOR: [
            Permission.TRACE_READ, Permission.TRACE_WRITE,
            Permission.DASHBOARD_READ, Permission.DASHBOARD_WRITE,
            Permission.ALERT_READ, Permission.ALERT_WRITE,
            Permission.EVALUATION_READ, Permission.EVALUATION_WRITE,
            Permission.ANALYTICS_READ,
            Permission.SAMPLING_READ,
            Permission.NOTIFICATION_READ,
            Permission.RETENTION_READ,
            Permission.TEAM_READ,
            Permission.ORG_READ,
        ],
        VIEWER: [
            Permission.TRACE_READ,
            Permission.DASHBOARD_READ,
            Permission.ALERT_READ,
            Permission.EVALUATION_READ,
            Permission.ANALYTICS_READ,
            Permission.SAMPLING_READ,
            Permission.NOTIFICATION_READ,
            Permission.RETENTION_READ,
            Permission.TEAM_READ,
            Permission.ORG_READ,
        ],
    }

    @classmethod
    def get_permissions(cls, role: str) -> List[str]:
        """Get permissions for a role."""
        perms = cls.PERMISSIONS.get(role, [])
        if perms == "all":
            return [v for v in vars(Permission).values() if isinstance(v, str) and ":" in v]
        return list(perms)

    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        """Check if a role has a specific permission."""
        if role == cls.OWNER:
            return True
        return permission in cls.get_permissions(role)


# ── Database Schema ─────────────────────────────────────


def _ensure_rbac_tables():
    """Create RBAC tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                org_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                settings TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                description TEXT,
                settings TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE,
                UNIQUE(org_id, slug)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                membership_id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                UNIQUE(team_id, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS org_members (
                membership_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                UNIQUE(org_id, user_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_org_id ON teams(org_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_team_id ON team_members(team_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_user_id ON team_members(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_org_members_org_id ON org_members(org_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_org_members_user_id ON org_members(user_id)")
        conn.commit()
    finally:
        conn.close()


# ── Organization CRUD ───────────────────────────────────


def create_organization(name: str, slug: str, description: str = "",
                        owner_user_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a new organization."""
    _ensure_rbac_tables()
    org_id = secrets.token_hex(8)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO organizations (org_id, name, slug, description) VALUES (?, ?, ?, ?)",
            (org_id, name, slug, description),
        )
        # Auto-add creator as owner
        if owner_user_id:
            membership_id = secrets.token_hex(8)
            conn.execute(
                "INSERT INTO org_members (membership_id, org_id, user_id, role) VALUES (?, ?, ?, ?)",
                (membership_id, org_id, owner_user_id, Role.OWNER),
            )
        conn.commit()
    except sqlite3.IntegrityError as e:
        if "slug" in str(e):
            raise ValueError(f"Organization slug '{slug}' already exists")
        raise
    finally:
        conn.close()

    return {"org_id": org_id, "name": name, "slug": slug, "description": description}


def get_organization(org_id: str) -> Optional[Dict[str, Any]]:
    """Get an organization by ID."""
    _ensure_rbac_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM organizations WHERE org_id = ?", (org_id,)).fetchone()
        if not row:
            return None
        org = dict(row)
        org["settings"] = json.loads(org["settings"]) if isinstance(org["settings"], str) else org["settings"]
        org["member_count"] = conn.execute(
            "SELECT COUNT(*) FROM org_members WHERE org_id = ?", (org_id,)
        ).fetchone()[0]
        org["team_count"] = conn.execute(
            "SELECT COUNT(*) FROM teams WHERE org_id = ?", (org_id,)
        ).fetchone()[0]
        return org
    finally:
        conn.close()


def list_organizations(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List organizations, optionally filtered by user membership."""
    _ensure_rbac_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if user_id:
            rows = conn.execute(
                """SELECT o.*, om.role as user_role
                   FROM organizations o
                   JOIN org_members om ON o.org_id = om.org_id
                   WHERE om.user_id = ?
                   ORDER BY o.name""",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM organizations ORDER BY name").fetchall()

        orgs = []
        for row in rows:
            org = dict(row)
            org["settings"] = json.loads(org["settings"]) if isinstance(org["settings"], str) else org["settings"]
            orgs.append(org)
        return orgs
    finally:
        conn.close()


def update_organization(org_id: str, data: Dict[str, Any]) -> bool:
    """Update an organization."""
    conn = sqlite3.connect(DB_PATH)
    try:
        sets = []
        params: list = []
        for key in ("name", "slug", "description", "settings"):
            if key in data:
                val = data[key]
                if key == "settings":
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                params.append(val)
        if not sets:
            return True
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(org_id)
        conn.execute(
            f"UPDATE organizations SET {', '.join(sets)} WHERE org_id = ?",
            params,
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update organization: {e}")
        return False
    finally:
        conn.close()


def delete_organization(org_id: str) -> bool:
    """Delete an organization and all associated teams/memberships."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM organizations WHERE org_id = ?", (org_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete organization: {e}")
        return False
    finally:
        conn.close()


# ── Team CRUD ───────────────────────────────────────────


def create_team(org_id: str, name: str, slug: str, description: str = "",
                creator_user_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a new team within an organization."""
    _ensure_rbac_tables()
    team_id = secrets.token_hex(8)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO teams (team_id, org_id, name, slug, description) VALUES (?, ?, ?, ?, ?)",
            (team_id, org_id, name, slug, description),
        )
        # Auto-add creator as owner
        if creator_user_id:
            membership_id = secrets.token_hex(8)
            conn.execute(
                "INSERT INTO team_members (membership_id, team_id, user_id, role) VALUES (?, ?, ?, ?)",
                (membership_id, team_id, creator_user_id, Role.OWNER),
            )
        conn.commit()
    except sqlite3.IntegrityError as e:
        if "slug" in str(e):
            raise ValueError(f"Team slug '{slug}' already exists in this organization")
        raise
    finally:
        conn.close()

    return {"team_id": team_id, "org_id": org_id, "name": name, "slug": slug, "description": description}


def get_team(team_id: str) -> Optional[Dict[str, Any]]:
    """Get a team by ID."""
    _ensure_rbac_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,)).fetchone()
        if not row:
            return None
        team = dict(row)
        team["settings"] = json.loads(team["settings"]) if isinstance(team["settings"], str) else team["settings"]
        team["member_count"] = conn.execute(
            "SELECT COUNT(*) FROM team_members WHERE team_id = ?", (team_id,)
        ).fetchone()[0]
        return team
    finally:
        conn.close()


def list_teams(org_id: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List teams, optionally filtered by org or user membership."""
    _ensure_rbac_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if user_id and org_id:
            rows = conn.execute(
                """SELECT t.*, tm.role as user_role
                   FROM teams t
                   JOIN team_members tm ON t.team_id = tm.team_id
                   WHERE t.org_id = ? AND tm.user_id = ?
                   ORDER BY t.name""",
                (org_id, user_id),
            ).fetchall()
        elif org_id:
            rows = conn.execute(
                "SELECT * FROM teams WHERE org_id = ? ORDER BY name", (org_id,)
            ).fetchall()
        elif user_id:
            rows = conn.execute(
                """SELECT t.*, tm.role as user_role, o.name as org_name
                   FROM teams t
                   JOIN team_members tm ON t.team_id = tm.team_id
                   JOIN organizations o ON t.org_id = o.org_id
                   WHERE tm.user_id = ?
                   ORDER BY t.name""",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM teams ORDER BY name").fetchall()

        teams = []
        for row in rows:
            team = dict(row)
            team["settings"] = json.loads(team["settings"]) if isinstance(team["settings"], str) else team["settings"]
            teams.append(team)
        return teams
    finally:
        conn.close()


def update_team(team_id: str, data: Dict[str, Any]) -> bool:
    """Update a team."""
    conn = sqlite3.connect(DB_PATH)
    try:
        sets = []
        params: list = []
        for key in ("name", "slug", "description", "settings"):
            if key in data:
                val = data[key]
                if key == "settings":
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                params.append(val)
        if not sets:
            return True
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(team_id)
        conn.execute(
            f"UPDATE teams SET {', '.join(sets)} WHERE team_id = ?",
            params,
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update team: {e}")
        return False
    finally:
        conn.close()


def delete_team(team_id: str) -> bool:
    """Delete a team and its memberships."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete team: {e}")
        return False
    finally:
        conn.close()


# ── Membership Management ───────────────────────────────


def add_org_member(org_id: str, user_id: str, role: str = "viewer") -> Dict[str, Any]:
    """Add a user to an organization."""
    _ensure_rbac_tables()
    membership_id = secrets.token_hex(8)

    if role not in (Role.OWNER, Role.ADMIN, Role.EDITOR, Role.VIEWER):
        raise ValueError(f"Invalid role: {role}")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO org_members (membership_id, org_id, user_id, role) VALUES (?, ?, ?, ?)",
            (membership_id, org_id, user_id, role),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("User is already a member of this organization")
    finally:
        conn.close()

    return {"membership_id": membership_id, "org_id": org_id, "user_id": user_id, "role": role}


def remove_org_member(org_id: str, user_id: str) -> bool:
    """Remove a user from an organization."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "DELETE FROM org_members WHERE org_id = ? AND user_id = ?",
            (org_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_org_member_role(org_id: str, user_id: str, role: str) -> bool:
    """Update a member's role in an organization."""
    if role not in (Role.OWNER, Role.ADMIN, Role.EDITOR, Role.VIEWER):
        raise ValueError(f"Invalid role: {role}")
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "UPDATE org_members SET role = ? WHERE org_id = ? AND user_id = ?",
            (role, org_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_org_members(org_id: str) -> List[Dict[str, Any]]:
    """List members of an organization."""
    _ensure_rbac_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT om.membership_id, om.org_id, om.user_id, om.role, om.joined_at,
                      u.username, u.display_name, u.email
               FROM org_members om
               JOIN users u ON om.user_id = u.user_id
               WHERE om.org_id = ?
               ORDER BY om.joined_at""",
            (org_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_team_member(team_id: str, user_id: str, role: str = "viewer") -> Dict[str, Any]:
    """Add a user to a team."""
    _ensure_rbac_tables()
    membership_id = secrets.token_hex(8)

    if role not in (Role.OWNER, Role.ADMIN, Role.EDITOR, Role.VIEWER):
        raise ValueError(f"Invalid role: {role}")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO team_members (membership_id, team_id, user_id, role) VALUES (?, ?, ?, ?)",
            (membership_id, team_id, user_id, role),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("User is already a member of this team")
    finally:
        conn.close()

    return {"membership_id": membership_id, "team_id": team_id, "user_id": user_id, "role": role}


def remove_team_member(team_id: str, user_id: str) -> bool:
    """Remove a user from a team."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "DELETE FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_team_member_role(team_id: str, user_id: str, role: str) -> bool:
    """Update a member's role in a team."""
    if role not in (Role.OWNER, Role.ADMIN, Role.EDITOR, Role.VIEWER):
        raise ValueError(f"Invalid role: {role}")
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "UPDATE team_members SET role = ? WHERE team_id = ? AND user_id = ?",
            (role, team_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_team_members(team_id: str) -> List[Dict[str, Any]]:
    """List members of a team."""
    _ensure_rbac_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT tm.membership_id, tm.team_id, tm.user_id, tm.role, tm.joined_at,
                      u.username, u.display_name, u.email
               FROM team_members tm
               JOIN users u ON tm.user_id = u.user_id
               WHERE tm.team_id = ?
               ORDER BY tm.joined_at""",
            (team_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Permission Checking ─────────────────────────────────


def get_user_permissions(user_id: str, org_id: Optional[str] = None,
                         team_id: Optional[str] = None) -> Dict[str, Any]:
    """Get effective permissions for a user in an org/team context.

    Returns the highest-level role and its permissions.
    """
    _ensure_rbac_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Check system-level role (admin in users table)
        user_row = conn.execute(
            "SELECT role FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        system_role = user_row["role"] if user_row else None

        # System admins have all permissions
        if system_role == "admin":
            return {
                "user_id": user_id,
                "system_role": system_role,
                "effective_role": Role.OWNER,
                "permissions": Role.get_permissions(Role.OWNER),
                "scope": "system",
            }

        # Check team-level role
        if team_id:
            team_row = conn.execute(
                "SELECT role FROM team_members WHERE team_id = ? AND user_id = ?",
                (team_id, user_id),
            ).fetchone()
            if team_row:
                return {
                    "user_id": user_id,
                    "system_role": system_role,
                    "team_role": team_row["role"],
                    "effective_role": team_row["role"],
                    "permissions": Role.get_permissions(team_row["role"]),
                    "scope": "team",
                    "team_id": team_id,
                }

        # Check org-level role
        if org_id:
            org_row = conn.execute(
                "SELECT role FROM org_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            ).fetchone()
            if org_row:
                return {
                    "user_id": user_id,
                    "system_role": system_role,
                    "org_role": org_row["role"],
                    "effective_role": org_row["role"],
                    "permissions": Role.get_permissions(org_row["role"]),
                    "scope": "org",
                    "org_id": org_id,
                }

        # Default: no org/team context, use system role
        return {
            "user_id": user_id,
            "system_role": system_role or "user",
            "effective_role": Role.VIEWER,
            "permissions": Role.get_permissions(Role.VIEWER),
            "scope": "global",
        }
    finally:
        conn.close()


def check_permission(user_id: str, permission: str,
                     org_id: Optional[str] = None,
                     team_id: Optional[str] = None) -> bool:
    """Check if a user has a specific permission in a given context."""
    perm_info = get_user_permissions(user_id, org_id=org_id, team_id=team_id)
    return permission in perm_info.get("permissions", [])


def get_user_teams(user_id: str) -> List[Dict[str, Any]]:
    """Get all teams a user belongs to, with org info."""
    _ensure_rbac_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT t.team_id, t.name as team_name, t.slug as team_slug,
                      t.org_id, o.name as org_name, o.slug as org_slug,
                      tm.role as team_role
               FROM team_members tm
               JOIN teams t ON tm.team_id = t.team_id
               JOIN organizations o ON t.org_id = o.org_id
               WHERE tm.user_id = ?
               ORDER BY o.name, t.name""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_orgs(user_id: str) -> List[Dict[str, Any]]:
    """Get all organizations a user belongs to, with role info."""
    _ensure_rbac_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT o.org_id, o.name as org_name, o.slug as org_slug,
                      om.role as org_role
               FROM org_members om
               JOIN organizations o ON om.org_id = o.org_id
               WHERE om.user_id = ?
               ORDER BY o.name""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
