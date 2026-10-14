# Connecting to ROAR (Penn State HPC) over SSH

## Host and authentication

- The local SSH config already defines `roar` as
  `submit.hpc.psu.edu`, user `zps5207`, using
  `~/.ssh/id_ed25519`.
- The private key is passphrase-protected. The user unlocks it in their own
  local Git Bash `ssh-agent`; never request, store, or transmit the
  passphrase.
- ROAR requires Duo/Microsoft MFA after successful key authentication. Every
  new connection produces a phone push that the user must physically approve.
  A delay or observation timeout can mean the push is awaiting approval; it is
  not by itself proof of authentication failure.
- Windows OpenSSH in this environment does not support usable
  ControlMaster/connection reuse. Every SSH or SCP call is a fresh connection
  and needs a fresh MFA approval.

## Required connection procedure

1. Ask the user to open their own local Git Bash window and ensure their
   `ssh-agent` is unlocked.
2. At that local prompt—not inside an active ROAR shell—the user runs:

   ```bash
   echo $SSH_AUTH_SOCK
   ```

   The user pastes the current socket path. The path is session-specific; do
   not reuse a value cached from an earlier session or terminal.
3. Immediately before connecting, tell the user that a Duo push is about to
   arrive and must be approved.
4. In the agent-controlled Git Bash shell, use the freshly supplied path and
   the configured alias:

   ```bash
   export SSH_AUTH_SOCK='<fresh path pasted by the user>'
   ssh -o ConnectTimeout=30 roar "<command>" </dev/null
   ```

5. Do **not** add `-o BatchMode=yes`. It suppresses the
   keyboard-interactive/MFA exchange and makes an MFA skip look like a
   permission failure.
6. Do **not** try ControlMaster or connection reuse. Expect a separate Duo push
   for every SSH/SCP connection.
7. If a connection reports a control-master or connection-reset error, inspect
   for stale ROAR-side `~/.ssh/sockets` state. Verify the exact target before
   removing that directory, then retry the known-good command above.
8. Do not thrash through alternate flags, keys, clients, or authentication
   approaches after a failure. Revalidate the fresh socket and repeat this
   procedure.

## Cluster execution policy

- Submit compute work through Slurm.
- Place all transferred files, run directories, and generated results beneath
  `/storage/home/zps5207/scratch`.
- Every `sbatch` submission requires the user's explicit approval for that
  specific submission, even when the SSH connection and job files are ready.
- Before each SSH/SCP call, warn the user about the new Duo push.

