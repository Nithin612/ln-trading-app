#!/usr/bin/env bash
#
# Is a backup destination ACTUALLY off-box?   ./scripts/offbox_check.sh SRC DEST
#
# ⛔⛔ Why this exists. On 2026-09-07 the dev database was destroyed with no backup of any
# kind. A backup now runs — to `/home/nithin/code/back_ups/trading_platform`, which `df` says
# is on `/dev/nvme0n1p5`: THE SAME PARTITION AS THE DATABASE. That copy survives exactly one
# failure mode, the logical wipe that actually happened, and none of the others. A disk
# failure, a filesystem corruption or an `rm -rf` on that partition takes the database and
# every backup of it together.
#
# ⭐ The point of this script is that "not really off-box" is INVISIBLE unless something
# checks. Nothing about a path tells you what device it lands on.
#
# Exit codes — deliberately graded rather than pass/fail, because the honest answer has more
# than two values:
#   0  OFFBOX     different physical device (or a network/removable mount)
#   3  SAME_DISK  different filesystem, SAME physical disk — survives fs corruption, NOT a
#                 disk failure. Better than nothing; not a backup.
#   4  SAME_FS    same filesystem. NOT A BACKUP DESTINATION AT ALL.
#   2  UNUSABLE   destination missing or unwritable
#
# ⚠ What it CANNOT tell you: whether a network mount is itself backed up, or whether a
# removable disk is physically in the same building. Device topology is the part that is
# checkable from here, so it is the part this checks — and the rest is said out loud rather
# than implied.
set -uo pipefail

SRC="${1:?usage: offbox_check.sh SRC DEST}"
DEST="${2:?usage: offbox_check.sh SRC DEST}"

[[ -d "$DEST" ]] || { echo "UNUSABLE  destination does not exist: $DEST"; exit 2; }
[[ -w "$DEST" ]] || { echo "UNUSABLE  destination not writable: $DEST"; exit 2; }
[[ -e "$SRC"  ]] || { echo "UNUSABLE  source does not exist: $SRC"; exit 2; }

src_fs="$(df --output=source "$SRC"  2>/dev/null | tail -1 | tr -d ' ')"
dst_fs="$(df --output=source "$DEST" 2>/dev/null | tail -1 | tr -d ' ')"

# `/dev/nvme0n1p5` -> `nvme0n1`;  `/dev/sda2` -> `sda`. A network or fuse mount has no such
# shape, which is why it falls through to OFFBOX rather than being forced into the comparison.
physical() {
  local d="${1#/dev/}"
  if   [[ "$d" =~ ^(nvme[0-9]+n[0-9]+)p[0-9]+$ ]]; then echo "${BASH_REMATCH[1]}"
  elif [[ "$d" =~ ^(mmcblk[0-9]+)p[0-9]+$      ]]; then echo "${BASH_REMATCH[1]}"
  elif [[ "$d" =~ ^([a-z]+)[0-9]+$             ]]; then echo "${BASH_REMATCH[1]}"
  else echo "$d"
  fi
}

if [[ "$src_fs" == "$dst_fs" ]]; then
  echo "SAME_FS  $DEST is on the same filesystem as $SRC ($src_fs) — NOT a backup destination"
  exit 4
fi

src_disk="$(physical "$src_fs")"
dst_disk="$(physical "$dst_fs")"
if [[ -n "$src_disk" && "$src_disk" == "$dst_disk" ]]; then
  echo "SAME_DISK  $dst_fs and $src_fs are both on $src_disk — survives fs corruption, not disk failure"
  exit 3
fi

echo "OFFBOX  $dst_fs is a different device from $src_fs"
exit 0
