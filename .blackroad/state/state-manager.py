#!/usr/bin/env python3
"""
BlackRoad State Manager
=======================

Manages state synchronization between:
- GitHub (source of truth for code)
- Cloudflare KV (fast state lookups)
- Salesforce (CRM tracking)

Architecture:
- GitHub holds the files and git history
- Cloudflare KV holds the current state (fast reads)
- Salesforce holds the business details (CRM data)

This creates a Salesforce-like project management experience in GitHub
while maintaining distributed state for performance and reliability.
"""

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class StateStatus(Enum):
    """Project/Task status values aligned with Kanban columns."""
    BACKLOG = "backlog"
    TRIAGE = "triage"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    STAGING = "staging"
    DONE = "done"


@dataclass
class StateRecord:
    """A state record that syncs across all backends."""
    id: str
    entity_type: str  # project, task, integration, deployment
    name: str
    status: StateStatus
    metadata: dict = field(default_factory=dict)
    github_ref: str | None = None  # Issue/PR number
    salesforce_id: str | None = None
    cloudflare_key: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    sha_hash: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "name": self.name,
            "status": self.status.value,
            "metadata": self.metadata,
            "github_ref": self.github_ref,
            "salesforce_id": self.salesforce_id,
            "cloudflare_key": self.cloudflare_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "sha_hash": self.sha_hash
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "StateRecord":
        return cls(
            id=data["id"],
            entity_type=data["entity_type"],
            name=data["name"],
            status=StateStatus(data["status"]),
            metadata=data.get("metadata", {}),
            github_ref=data.get("github_ref"),
            salesforce_id=data.get("salesforce_id"),
            cloudflare_key=data.get("cloudflare_key"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            sha_hash=data.get("sha_hash")
        )


class StateBackend(ABC):
    """Abstract base class for state backends."""

    @abstractmethod
    def get(self, key: str) -> StateRecord | None:
        """Get a state record by key."""
        pass

    @abstractmethod
    def put(self, record: StateRecord) -> bool:
        """Store a state record."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a state record."""
        pass

    @abstractmethod
    def list(self, prefix: str = "") -> list[StateRecord]:
        """List all state records with optional prefix filter."""
        pass


class CloudflareKVBackend(StateBackend):
    """
    Cloudflare KV state backend.

    Fast, globally distributed state storage.
    Perfect for real-time state lookups.
    """

    def __init__(self, account_id: str | None = None, namespace_id: str | None = None,
                 api_token: str | None = None):
        self.account_id = account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        self.namespace_id = namespace_id or os.environ.get("CLOUDFLARE_KV_NAMESPACE_ID")
        self.api_token = api_token or os.environ.get("CLOUDFLARE_API_TOKEN")
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/storage/kv/namespaces/{self.namespace_id}"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def get(self, key: str) -> StateRecord | None:
        """Get a state record from Cloudflare KV."""
        try:
            import requests
            response = requests.get(
                f"{self.base_url}/values/{key}",
                headers=self._headers()
            )
            if response.status_code == 200:
                return StateRecord.from_dict(response.json())
            return None
        except Exception as e:
            print(f"Cloudflare KV get error: {e}")
            return None

    def put(self, record: StateRecord) -> bool:
        """Store a state record in Cloudflare KV."""
        try:
            import requests
            key = record.cloudflare_key or f"{record.entity_type}:{record.id}"
            record.cloudflare_key = key
            record.updated_at = time.time()

            response = requests.put(
                f"{self.base_url}/values/{key}",
                headers=self._headers(),
                data=record.to_json()
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Cloudflare KV put error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete a state record from Cloudflare KV."""
        try:
            import requests
            response = requests.delete(
                f"{self.base_url}/values/{key}",
                headers=self._headers()
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Cloudflare KV delete error: {e}")
            return False

    def list(self, prefix: str = "") -> list[StateRecord]:
        """List all state records in Cloudflare KV."""
        try:
            import requests
            params = {"prefix": prefix} if prefix else {}
            response = requests.get(
                f"{self.base_url}/keys",
                headers=self._headers(),
                params=params
            )
            if response.status_code == 200:
                data = response.json()
                records = []
                for key_info in data.get("result", []):
                    record = self.get(key_info["name"])
                    if record:
                        records.append(record)
                return records
            return []
        except Exception as e:
            print(f"Cloudflare KV list error: {e}")
            return []


class SalesforceBackend(StateBackend):
    """
    Salesforce CRM backend.

    Stores business context, relationships, and detailed metadata.
    Maps GitHub entities to Salesforce objects.
    """

    def __init__(self, instance_url: str | None = None, access_token: str | None = None):
        self.instance_url = instance_url or os.environ.get("SF_INSTANCE_URL")
        self.access_token = access_token or os.environ.get("SF_ACCESS_TOKEN")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _object_name(self, entity_type: str) -> str:
        """Map entity types to Salesforce object names."""
        mapping = {
            "project": "Project__c",
            "task": "Task__c",
            "integration": "Integration__c",
            "deployment": "Deployment__c"
        }
        return mapping.get(entity_type, "Task__c")

    def get(self, key: str) -> StateRecord | None:
        """Get a state record from Salesforce."""
        try:
            import requests
            # Parse key format: entity_type:id
            parts = key.split(":")
            if len(parts) != 2:
                return None

            entity_type, sf_id = parts
            obj_name = self._object_name(entity_type)

            response = requests.get(
                f"{self.instance_url}/services/data/v58.0/sobjects/{obj_name}/{sf_id}",
                headers=self._headers()
            )

            if response.status_code == 200:
                data = response.json()
                return StateRecord(
                    id=data.get("Id"),
                    entity_type=entity_type,
                    name=data.get("Name", ""),
                    status=StateStatus(data.get("Status__c", "backlog")),
                    metadata=data,
                    salesforce_id=data.get("Id"),
                    github_ref=data.get("GitHub_Ref__c")
                )
            return None
        except Exception as e:
            print(f"Salesforce get error: {e}")
            return None

    def put(self, record: StateRecord) -> bool:
        """Store a state record in Salesforce."""
        try:
            import requests
            obj_name = self._object_name(record.entity_type)

            sf_data = {
                "Name": record.name[:80],  # Salesforce name limit
                "Status__c": record.status.value,
                "GitHub_Ref__c": record.github_ref,
                "SHA_Hash__c": record.sha_hash,
                "Last_Sync__c": datetime.utcnow().isoformat()
            }

            if record.salesforce_id:
                # Update existing
                response = requests.patch(
                    f"{self.instance_url}/services/data/v58.0/sobjects/{obj_name}/{record.salesforce_id}",
                    headers=self._headers(),
                    json=sf_data
                )
                return response.status_code in [200, 204]
            else:
                # Create new
                response = requests.post(
                    f"{self.instance_url}/services/data/v58.0/sobjects/{obj_name}",
                    headers=self._headers(),
                    json=sf_data
                )
                if response.status_code == 201:
                    record.salesforce_id = response.json().get("id")
                    return True
                return False
        except Exception as e:
            print(f"Salesforce put error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete a state record from Salesforce."""
        try:
            import requests
            parts = key.split(":")
            if len(parts) != 2:
                return False

            entity_type, sf_id = parts
            obj_name = self._object_name(entity_type)

            response = requests.delete(
                f"{self.instance_url}/services/data/v58.0/sobjects/{obj_name}/{sf_id}",
                headers=self._headers()
            )
            return response.status_code == 204
        except Exception as e:
            print(f"Salesforce delete error: {e}")
            return False

    def list(self, prefix: str = "") -> list[StateRecord]:
        """List state records from Salesforce using SOQL."""
        try:
            import requests

            # Determine object type from prefix
            entity_type = prefix.split(":")[0] if ":" in prefix else "task"
            obj_name = self._object_name(entity_type)

            query = f"SELECT Id, Name, Status__c, GitHub_Ref__c, SHA_Hash__c FROM {obj_name} LIMIT 200"

            response = requests.get(
                f"{self.instance_url}/services/data/v58.0/query",
                headers=self._headers(),
                params={"q": query}
            )

            if response.status_code == 200:
                data = response.json()
                records = []
                for item in data.get("records", []):
                    records.append(StateRecord(
                        id=item["Id"],
                        entity_type=entity_type,
                        name=item["Name"],
                        status=StateStatus(item.get("Status__c", "backlog")),
                        salesforce_id=item["Id"],
                        github_ref=item.get("GitHub_Ref__c"),
                        sha_hash=item.get("SHA_Hash__c")
                    ))
                return records
            return []
        except Exception as e:
            print(f"Salesforce list error: {e}")
            return []


class LocalFileBackend(StateBackend):
    """
    Local file backend for development/testing.

    Stores state in JSON files in .blackroad/state/data/
    """

    def __init__(self, base_path: str = ".blackroad/state/data"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def _file_path(self, key: str) -> str:
        # Sanitize key for filesystem
        safe_key = key.replace(":", "_").replace("/", "_")
        return os.path.join(self.base_path, f"{safe_key}.json")

    def get(self, key: str) -> StateRecord | None:
        try:
            path = self._file_path(key)
            if os.path.exists(path):
                with open(path, "r") as f:
                    return StateRecord.from_dict(json.load(f))
            return None
        except Exception as e:
            print(f"Local get error: {e}")
            return None

    def put(self, record: StateRecord) -> bool:
        try:
            key = record.cloudflare_key or f"{record.entity_type}:{record.id}"
            record.cloudflare_key = key
            record.updated_at = time.time()

            path = self._file_path(key)
            with open(path, "w") as f:
                json.dump(record.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Local put error: {e}")
            return False

    def delete(self, key: str) -> bool:
        try:
            path = self._file_path(key)
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception as e:
            print(f"Local delete error: {e}")
            return False

    def list(self, prefix: str = "") -> list[StateRecord]:
        try:
            records = []
            for filename in os.listdir(self.base_path):
                if filename.endswith(".json"):
                    if not prefix or filename.startswith(prefix.replace(":", "_")):
                        with open(os.path.join(self.base_path, filename), "r") as f:
                            records.append(StateRecord.from_dict(json.load(f)))
            return records
        except Exception as e:
            print(f"Local list error: {e}")
            return []


class StateManager:
    """
    Unified state manager that synchronizes across all backends.

    Primary: Cloudflare KV (fast reads)
    Secondary: Salesforce (CRM data)
    Fallback: Local file (development)
    """

    def __init__(self, use_cloudflare: bool = True, use_salesforce: bool = True):
        self.backends: list[StateBackend] = []

        # Always have local backend as fallback
        self.local = LocalFileBackend()
        self.backends.append(self.local)

        # Add Cloudflare if configured
        if use_cloudflare and os.environ.get("CLOUDFLARE_API_TOKEN"):
            self.cloudflare = CloudflareKVBackend()
            self.backends.insert(0, self.cloudflare)

        # Add Salesforce if configured
        if use_salesforce and os.environ.get("SF_ACCESS_TOKEN"):
            self.salesforce = SalesforceBackend()
            self.backends.append(self.salesforce)

    def get(self, key: str) -> StateRecord | None:
        """Get from first available backend."""
        for backend in self.backends:
            record = backend.get(key)
            if record:
                return record
        return None

    def put(self, record: StateRecord) -> bool:
        """Put to all backends."""
        success = True
        for backend in self.backends:
            if not backend.put(record):
                success = False
                print(f"Failed to sync to {backend.__class__.__name__}")
        return success

    def delete(self, key: str) -> bool:
        """Delete from all backends."""
        success = True
        for backend in self.backends:
            if not backend.delete(key):
                success = False
        return success

    def sync(self) -> dict:
        """
        Synchronize state across all backends.

        Returns sync report with any conflicts or failures.
        """
        report = {
            "timestamp": time.time(),
            "synced": 0,
            "conflicts": [],
            "errors": []
        }

        # Get all records from local (source of truth for development)
        local_records = self.local.list()

        for record in local_records:
            for backend in self.backends:
                if backend != self.local:
                    try:
                        backend.put(record)
                        report["synced"] += 1
                    except Exception as e:
                        report["errors"].append({
                            "record": record.id,
                            "backend": backend.__class__.__name__,
                            "error": str(e)
                        })

        return report

    def create_task(self, name: str, github_ref: str | None = None) -> StateRecord:
        """Helper to create a new task record."""
        import uuid
        record = StateRecord(
            id=str(uuid.uuid4())[:8],
            entity_type="task",
            name=name,
            status=StateStatus.TODO,
            github_ref=github_ref
        )
        self.put(record)
        return record

    def update_status(self, key: str, status: StateStatus) -> bool:
        """Update the status of a record."""
        record = self.get(key)
        if record:
            record.status = status
            record.updated_at = time.time()
            return self.put(record)
        return False


# CLI interface
if __name__ == "__main__":
    import sys

    manager = StateManager(use_cloudflare=False, use_salesforce=False)

    if len(sys.argv) < 2:
        print("Usage: state-manager.py <command> [args]")
        print("\nCommands:")
        print("  list [prefix]        - List all state records")
        print("  get <key>            - Get a specific record")
        print("  create <name>        - Create a new task")
        print("  status <key> <status> - Update status")
        print("  sync                 - Sync all backends")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        prefix = sys.argv[2] if len(sys.argv) > 2 else ""
        records = manager.local.list(prefix)
        for record in records:
            print(f"[{record.status.value:12}] {record.id}: {record.name}")

    elif command == "get":
        key = sys.argv[2]
        record = manager.get(key)
        if record:
            print(record.to_json())
        else:
            print(f"Record not found: {key}")

    elif command == "create":
        name = " ".join(sys.argv[2:])
        record = manager.create_task(name)
        print(f"Created task: {record.id}")
        print(record.to_json())

    elif command == "status":
        key = sys.argv[2]
        status = StateStatus(sys.argv[3])
        if manager.update_status(key, status):
            print(f"Updated {key} to {status.value}")
        else:
            print(f"Failed to update {key}")

    elif command == "sync":
        report = manager.sync()
        print(json.dumps(report, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
