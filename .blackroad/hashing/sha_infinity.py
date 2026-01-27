#!/usr/bin/env python3
"""
BlackRoad SHA-Infinity Hashing System
=====================================

SHA-Infinity is a recursive, layered hashing algorithm that provides:
1. Standard SHA-256 base hashing
2. Iterative deepening with configurable depth
3. Cross-reference hashing for integrity chains
4. Merkle tree construction for file sets
5. State fingerprinting for sync validation

This ensures PR integrity and cross-repo consistency.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HashResult:
    """Result of a hashing operation."""
    sha256: str
    sha_infinity: str
    depth: int
    timestamp: float
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sha256": self.sha256,
            "sha_infinity": self.sha_infinity,
            "depth": self.depth,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class SHAInfinity:
    """
    SHA-Infinity: Recursive layered hashing for integrity verification.

    The "infinity" aspect comes from the ability to chain hashes indefinitely,
    creating a verifiable history of changes that can be traced back to origin.
    """

    DEFAULT_DEPTH = 7  # Lucky number, good balance of security/performance
    MAX_DEPTH = 256    # Absolute maximum to prevent DoS
    SALT_PREFIX = "blackroad::"

    def __init__(self, depth: int = DEFAULT_DEPTH, salt: str = ""):
        """
        Initialize SHA-Infinity hasher.

        Args:
            depth: Number of recursive hash iterations (1-256)
            salt: Optional salt for domain separation
        """
        self.depth = min(max(depth, 1), self.MAX_DEPTH)
        self.salt = salt or self.SALT_PREFIX

    def sha256(self, data: bytes | str) -> str:
        """Standard SHA-256 hash."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha256(data).hexdigest()

    def sha_infinity(self, data: bytes | str, depth: int | None = None) -> str:
        """
        SHA-Infinity recursive hash.

        Each iteration takes the previous hash and re-hashes it with
        the iteration number, creating a chain that's computationally
        expensive to reverse but cheap to verify.

        Args:
            data: Data to hash
            depth: Override default depth

        Returns:
            Final hash after all iterations
        """
        if isinstance(data, str):
            data = data.encode('utf-8')

        iterations = depth or self.depth

        # Initial hash with salt
        current_hash = hashlib.sha256(
            f"{self.salt}:0:".encode() + data
        ).hexdigest()

        # Recursive deepening
        for i in range(1, iterations + 1):
            # Each iteration includes: salt, iteration number, previous hash
            to_hash = f"{self.salt}:{i}:{current_hash}".encode()
            current_hash = hashlib.sha256(to_hash).hexdigest()

        return current_hash

    def hash_file(self, filepath: str | Path) -> HashResult:
        """
        Hash a file with both SHA-256 and SHA-Infinity.

        Args:
            filepath: Path to file

        Returns:
            HashResult with both hashes and metadata
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        content = filepath.read_bytes()

        return HashResult(
            sha256=self.sha256(content),
            sha_infinity=self.sha_infinity(content),
            depth=self.depth,
            timestamp=time.time(),
            metadata={
                "filename": filepath.name,
                "size": len(content),
                "path": str(filepath)
            }
        )

    def hash_directory(self, dirpath: str | Path, pattern: str = "**/*") -> HashResult:
        """
        Create a Merkle-style hash of a directory.

        Hashes all files matching pattern and combines them into
        a single integrity hash.

        Args:
            dirpath: Directory path
            pattern: Glob pattern for files to include

        Returns:
            Combined HashResult
        """
        dirpath = Path(dirpath)

        if not dirpath.is_dir():
            raise NotADirectoryError(f"Not a directory: {dirpath}")

        # Collect all file hashes
        file_hashes = []
        files_processed = []

        for filepath in sorted(dirpath.glob(pattern)):
            if filepath.is_file():
                file_hash = self.sha256(filepath.read_bytes())
                relative_path = str(filepath.relative_to(dirpath))
                file_hashes.append(f"{relative_path}:{file_hash}")
                files_processed.append(relative_path)

        # Combine into single hash
        combined = "\n".join(file_hashes)

        return HashResult(
            sha256=self.sha256(combined),
            sha_infinity=self.sha_infinity(combined),
            depth=self.depth,
            timestamp=time.time(),
            metadata={
                "directory": str(dirpath),
                "file_count": len(files_processed),
                "files": files_processed[:100],  # Limit for large dirs
                "pattern": pattern
            }
        )

    def hash_git_state(self, repo_path: str | Path = ".") -> HashResult:
        """
        Create integrity hash of current git state.

        Combines HEAD commit, staged changes, and working directory
        state into a single verifiable hash.

        Args:
            repo_path: Path to git repository

        Returns:
            HashResult representing git state
        """
        import subprocess

        repo_path = Path(repo_path)

        def run_git(args: list[str]) -> str:
            result = subprocess.run(
                ["git"] + args,
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()

        # Gather git state components
        head_commit = run_git(["rev-parse", "HEAD"])
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        staged_diff = run_git(["diff", "--cached", "--stat"])
        working_diff = run_git(["diff", "--stat"])

        # Combine state
        state_string = f"""
HEAD: {head_commit}
BRANCH: {branch}
STAGED:
{staged_diff}
WORKING:
{working_diff}
"""

        return HashResult(
            sha256=self.sha256(state_string),
            sha_infinity=self.sha_infinity(state_string),
            depth=self.depth,
            timestamp=time.time(),
            metadata={
                "head": head_commit,
                "branch": branch,
                "has_staged_changes": bool(staged_diff),
                "has_working_changes": bool(working_diff)
            }
        )

    def verify_chain(self, data: bytes | str, expected_hash: str,
                     max_depth: int = MAX_DEPTH) -> tuple[bool, int]:
        """
        Verify data against a SHA-Infinity hash by trying different depths.

        Useful when depth is unknown but hash is known.

        Args:
            data: Original data
            expected_hash: Expected SHA-Infinity hash
            max_depth: Maximum depth to try

        Returns:
            Tuple of (is_valid, depth_found)
        """
        for depth in range(1, min(max_depth, self.MAX_DEPTH) + 1):
            if self.sha_infinity(data, depth=depth) == expected_hash:
                return (True, depth)
        return (False, -1)

    def create_integrity_manifest(self, paths: list[str | Path]) -> dict:
        """
        Create an integrity manifest for multiple files/directories.

        This is used for PR validation and cross-repo consistency checks.

        Args:
            paths: List of file/directory paths

        Returns:
            Manifest dictionary
        """
        manifest = {
            "version": "1.0",
            "algorithm": "sha-infinity",
            "depth": self.depth,
            "created": time.time(),
            "entries": []
        }

        for path in paths:
            path = Path(path)
            if path.is_file():
                result = self.hash_file(path)
            elif path.is_dir():
                result = self.hash_directory(path)
            else:
                continue

            manifest["entries"].append({
                "path": str(path),
                "type": "file" if path.is_file() else "directory",
                **result.to_dict()
            })

        # Create manifest hash
        manifest_content = json.dumps(manifest["entries"], sort_keys=True)
        manifest["manifest_hash"] = self.sha_infinity(manifest_content)

        return manifest


# Convenience functions for CLI usage
def hash_string(data: str, depth: int = 7) -> str:
    """Quick hash of a string."""
    return SHAInfinity(depth=depth).sha_infinity(data)


def hash_file(filepath: str, depth: int = 7) -> dict:
    """Quick hash of a file."""
    return SHAInfinity(depth=depth).hash_file(filepath).to_dict()


def verify_file(filepath: str, expected_hash: str) -> bool:
    """Verify a file against expected hash."""
    hasher = SHAInfinity()
    result = hasher.hash_file(filepath)
    return result.sha_infinity == expected_hash


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: sha_infinity.py <file_or_string> [depth]")
        print("\nExamples:")
        print("  sha_infinity.py 'hello world'")
        print("  sha_infinity.py ./myfile.txt 10")
        print("  sha_infinity.py --dir ./src")
        print("  sha_infinity.py --git")
        sys.exit(1)

    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    hasher = SHAInfinity(depth=depth)

    if sys.argv[1] == "--git":
        result = hasher.hash_git_state()
        print(result.to_json())
    elif sys.argv[1] == "--dir":
        dirpath = sys.argv[2] if len(sys.argv) > 2 else "."
        result = hasher.hash_directory(dirpath)
        print(result.to_json())
    elif os.path.isfile(sys.argv[1]):
        result = hasher.hash_file(sys.argv[1])
        print(result.to_json())
    else:
        result = HashResult(
            sha256=hasher.sha256(sys.argv[1]),
            sha_infinity=hasher.sha_infinity(sys.argv[1]),
            depth=depth,
            timestamp=time.time(),
            metadata={"input": sys.argv[1][:100]}
        )
        print(result.to_json())
