# Backup safety and recovery

ForgeKit's backup commands are designed for convenience, not as a replacement for
`restic`, `borg`, `rsync` snapshots or filesystem snapshots. This page explains
exactly what the implementation guarantees, what it does not, and how to recover
if something goes wrong.

## Creating a backup

`forge backup create SOURCE [DEST] [--compression gz|bz2|xz|none] [--dry-run] [--json]`

Guarantees:

- Files are streamed into a temporary file next to the destination and published
  with an atomic hard link, so an interrupted run never leaves a
  half-written archive at the destination name.
- An existing archive is never overwritten (`FileExistsError`).
- A destination inside the source tree is rejected.
- Symlinks and special files (devices, FIFOs, sockets) in the source are
  **refused**, not silently skipped: a backup that silently drops a directory is
  worse than a backup that fails.
- Hard-linked source files are stored as independent regular files.
- Each regular file is opened with `O_NOFOLLOW` and checked for identity, size and
  mtime before being added; a source that changes during the run fails the
  backup instead of producing a misleading archive.
- The SHA-256 of the finished archive is printed and included in the JSON
  manifest.

Not guaranteed:

- **Consistency.** A backup of a directory that is being written to is not a
  filesystem snapshot. Use an LVM, ZFS, btrfs or VM snapshot for live data.
- Any protection against a compromised source or a compromised machine.

## Verifying a backup

`forge backup verify ARCHIVE [--sha256 DIGEST]`

Verification:

1. Reads every member, including compressed trailers, to detect truncation and
   corruption.
2. Enforces the archive policy: only regular files and directories, no absolute
   paths, no `..`, no backslashes, no drive letters, no duplicate paths, no
   sparse members, no links or special files.
3. Optionally compares the archive bytes against a SHA-256 digest you stored
   somewhere else.

A SHA-256 comparison proves that the *bytes* match the value you trust. It is not
a signature: anyone who can modify the archive can also change a digest stored
next to it. Save the digest in a separate system, ticket or password manager.

## Restoring a backup

`forge backup restore ARCHIVE DEST [--dry-run] [--force] [--json]`

### Preflight (always read-only)

- The archive is opened without following a symlink and must be a regular file.
- Its contents are parsed and validated against the policy above; conflicts with
  existing destination state are reported (`would_overwrite`, `conflict_count`).
- `--dry-run` stops here and creates nothing — no scratch file, no destination,
  no parent directories.
- Restoring over the archive itself is rejected.

### Safe extraction

- Without `--force`, conflicts make the command exit 1 with
  `status: "needs_confirmation"` and no writes.
- With `--force`, only **regular files** may be replaced. Existing symlinks,
  directories in place of files, devices and FIFOs are refused.
- The archive is copied into a private temporary file, verified, and extracted
  from that snapshot, so replacing the original path mid-restore cannot change
  what is written.
- Every directory is opened relative to a pinned root descriptor with
  `O_NOFOLLOW`; symlinks in the destination or any ancestor are refused at every
  step, including when they appear during the restore.
- Files are written to a random temporary name and published by hard link
  (`EEXIST` protects concurrent creation) or `os.replace` after an explicit
  `--force`.
- Requires POSIX `dir_fd` and `O_NOFOLLOW` support; it fails closed elsewhere.
  Listing, verification and dry runs still work.

### Rollback journal

While restoring, ForgeKit records every change in a private
`.forgekit-restore-<random>` directory inside the destination root:

- an existing regular file replaced under `--force` is **renamed** into the
  journal before the new file is published (same filesystem, no extra space, the
  original inode and mode are preserved);
- newly created files and directories — including destination parents created by
  this run — are recorded.

If any member fails (disk full, permission error, I/O error, Ctrl+C), the journal
is replayed in reverse: new files are removed, originals are renamed back, and
created directories are removed if they are empty. The command then exits 1 and
reports:

```json
{"error": "restore aborted; the destination was rolled back to its previous state: ...",
 "rolled_back": true, "rollback_errors": []}
```

If the undo itself fails, ForgeKit reports `rolled_back: false`, lists the
individual problems and tells you to inspect the destination. It never claims a
rollback that did not happen.

On success the journal is deleted: replacing those files is the explicit effect
of `--force`. Each replaced file is counted in the result (`overwritten`).

### What is not restored or not guaranteed

| Item | Status |
|------|--------|
| File contents | Restored |
| Regular-file permission bits | Restored (setuid/setgid/sticky bits are stripped) |
| Directory permissions | Not restored (created as `0755`) |
| Ownership | Not restored |
| Timestamps (mtime/atime) | Not restored |
| ACLs, extended attributes, SELinux labels, capabilities | Not restored |
| Symlinks, hard links, devices, FIFOs | Refused by policy |
| Crash atomicity | Not guaranteed (see below) |
| Durability after power loss | Not guaranteed; content is not `fsync`ed |

### Interrupted restores

If the process is killed with `SIGKILL`, the machine loses power, or the
filesystem itself fails:

1. Look for a `.forgekit-restore-<random>` directory in the destination root. It
   contains the original files that were being replaced; rename them back over
   the new files if you prefer the originals.
2. Files without an entry in the journal are newly restored files; delete them if
   you want to start again.
3. Re-run `forge backup verify ARCHIVE --sha256 DIGEST` and then
   `forge backup restore ... --dry-run` before retrying.
4. Never delete your only copy of the archive while the destination is in an
   unknown state.

## Resource limits

| Limit | Value |
|-------|-------|
| Archive members | 100,000 |
| Path length / components | 4,096 characters / 128 |
| Metadata header per member | 1 MiB |
| Archive size | 1 TiB |
| Expanded (decompressed) size | 1 TiB |
| Sparse members | Rejected |
| Compression | gzip, bzip2, xz, none |
| HTTP/timeout relevance | none (local I/O only) |

Restore additionally needs free space in `TMPDIR` roughly equal to the archive
plus a 64 MiB reserve for the verification snapshot. Set `TMPDIR` to a private
filesystem with enough room, or restore from an archive on the destination
filesystem.

## Threat model

- Archives are untrusted input: the parser is treated as hostile, sizes and
  metadata are bounded before allocation, and extraction never follows links.
- Restore never executes content, never sets special permission bits, and never
  writes outside the destination.
- A local attacker who controls the destination directory can still make a
  restore fail; the journal is best-effort protection against that, not a
  security boundary.
- Confidentiality is your responsibility: archives are not encrypted. Use an
  encrypted container or another tool if the backup contains sensitive data.

## Checklist before relying on a backup

1. `forge backup verify ARCHIVE` succeeds.
2. The SHA-256 is stored somewhere separate and trusted.
3. `forge backup restore ARCHIVE /tmp/restore-test --dry-run` looks correct.
4. A real restore into an empty directory reproduces the files you expect.
5. You have a second copy of anything irreplaceable (3-2-1 rule).
