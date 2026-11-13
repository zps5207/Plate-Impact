#!/usr/bin/env node
// sessions-script-version: 1
//
// Session ledger + packaging tool. AI Terminal records every pane session into
// agents/sessions/<id>/ (session.json + transcript.log). This script reads that
// ledger and can package sessions, commit them and push, in one go.
//
//   node agents/sessions/sessions.mjs status
//   node agents/sessions/sessions.mjs list
//   node agents/sessions/sessions.mjs tail <session-id> [lines]
//   node agents/sessions/sessions.mjs ship [selectors] [options]
//
// ship selectors (default: every ended session not yet packaged):
//   --sessions S-1,S-2   only these sessions
//   --all                also stage dirty files no session claims
//   --include-open       include sessions whose pane is still running
// ship options:
//   --message "text"     commit subject (default is generated)
//   --trailer "K: v"     extra commit trailer, repeatable
//   --note "text"        free-text note recorded in the package file
//   --push               push after committing (never forced)
//   --dry-run            print the plan, change nothing
//   --allow-prestaged    do not abort when other files are already staged

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const SESSIONS_DIR = path.dirname(fileURLToPath(import.meta.url))
const PROJECT_DIR = path.resolve(SESSIONS_DIR, '..', '..')
const SESSIONS_REL = 'agents/sessions'
// Outcome states that mean a session needs no further packaging.
const DONE = new Set(['committed', 'nothing-to-commit'])
const SENSITIVE = /(^|\/)(\.env(\..*)?|[^/]*\.(pem|key|p12|pfx)|id_(rsa|ed25519|ecdsa)|credentials(\..*)?|[^/]*secret[^/]*)$/i

function die(msg) { console.error(`error: ${msg}`); process.exit(1) }

function gitIn(dir, args, opts = {}) {
  return execFileSync('git', ['-C', dir, ...args], { encoding: 'utf8', maxBuffer: 256 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'], ...opts })
}

let ROOT
try { ROOT = gitIn(PROJECT_DIR, ['rev-parse', '--show-toplevel']).trim() } catch { die('this project is not a git repository') }
const git = (args, opts) => gitIn(ROOT, args, opts)

// ── ledger ───────────────────────────────────────────────────────────────────

function loadSessions() {
  if (!fs.existsSync(SESSIONS_DIR)) return []
  const out = []
  for (const name of fs.readdirSync(SESSIONS_DIR)) {
    if (!name.startsWith('S-')) continue
    const file = path.join(SESSIONS_DIR, name, 'session.json')
    try { out.push({ ...JSON.parse(fs.readFileSync(file, 'utf8')), _file: file }) }
    catch { /* unreadable manifest: skip, status reports the count */ }
  }
  return out.sort((a, b) => a.startedAt.localeCompare(b.startedAt))
}

function saveSession(s) {
  const { _file, ...data } = s
  fs.writeFileSync(_file, JSON.stringify(data, null, 2) + '\n')
}

const stateOf = (s) => s.outcome?.state ?? 'unpackaged'
const fmt = (iso) => (iso ? iso.replace('T', ' ').slice(0, 16) : '-')
function duration(s) {
  if (!s.endedAt) return 'running'
  const m = Math.round((Date.parse(s.endedAt) - Date.parse(s.startedAt)) / 60000)
  return m < 1 ? '<1m' : m < 60 ? `${m}m` : `${Math.floor(m / 60)}h${String(m % 60).padStart(2, '0')}m`
}

// ── git helpers ──────────────────────────────────────────────────────────────

// Parses `git status --porcelain=v1 -z`: "XY path\0", renames add "orig\0".
function dirtyNow() {
  const raw = git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])
  const parts = raw.split('\0')
  const files = []
  for (let i = 0; i < parts.length; i++) {
    const e = parts[i]
    if (e.length < 4) continue
    const xy = e.slice(0, 2)
    files.push({ path: e.slice(3), xy })
    if (xy[0] === 'R' || xy[0] === 'C') i++
  }
  return files.filter(f => !f.path.startsWith(`${relFromRoot(SESSIONS_DIR)}/`))
}

function relFromRoot(abs) { return path.relative(ROOT, abs).split(path.sep).join('/') }

function branchInfo() {
  const branch = git(['rev-parse', '--abbrev-ref', 'HEAD']).trim()
  let upstream = null, ahead = 0, behind = 0
  try {
    upstream = git(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']).trim()
    const [a, b] = git(['rev-list', '--left-right', '--count', 'HEAD...@{u}']).trim().split(/\s+/).map(Number)
    ahead = a; behind = b
  } catch { /* no upstream */ }
  return { branch, upstream, ahead, behind }
}

function chunked(list, n = 80) {
  const out = []
  for (let i = 0; i < list.length; i += n) out.push(list.slice(i, i + n))
  return out
}

// ── commands ─────────────────────────────────────────────────────────────────

function cmdList() {
  const sessions = loadSessions()
  if (!sessions.length) return console.log('No sessions recorded yet.')
  console.log('ID'.padEnd(26), 'ROLE'.padEnd(8), 'STARTED'.padEnd(17), 'LENGTH'.padEnd(8), 'ENDED BY'.padEnd(10), 'FILES'.padEnd(6), 'STATE')
  for (const s of sessions) {
    const files = (s.uncommittedFiles?.length ?? 0)
    console.log(s.id.padEnd(26), s.role.padEnd(8), fmt(s.startedAt).padEnd(17), duration(s).padEnd(8),
      (s.endReason ?? 'running').padEnd(10), String(files).padEnd(6), stateOf(s) + (s.outcome?.reason ? ` (${s.outcome.reason})` : ''))
  }
}

function cmdStatus() {
  const sessions = loadSessions()
  const info = branchInfo()
  const dirty = dirtyNow()
  console.log(`Branch ${info.branch}${info.upstream ? ` -> ${info.upstream} (ahead ${info.ahead}, behind ${info.behind})` : ' (no upstream)'}`)
  console.log(`Working tree: ${dirty.length} dirty file(s) outside ${SESSIONS_REL}`)
  const pending = sessions.filter(s => !DONE.has(stateOf(s)))
  const open = pending.filter(s => !s.endedAt)
  const ended = pending.filter(s => s.endedAt)
  const claimed = new Set(ended.flatMap(s => (s.uncommittedFiles ?? []).map(f => f.path)))
  const unclaimed = dirty.filter(d => !claimed.has(d.path))
  console.log(`Sessions: ${sessions.length} recorded, ${sessions.length - pending.length} packaged, ${ended.length} ended and waiting, ${open.length} still running`)
  for (const s of ended) {
    const why = s.outcome?.reason ? `; last attempt: ${stateOf(s)} (${s.outcome.reason})` : ''
    const crash = s.endReason === 'crashed' ? '; app closed unexpectedly' : ''
    console.log(`  ${s.id}  ${s.role}  ${duration(s)}  ${s.uncommittedFiles?.length ?? 0} uncommitted file(s)${crash}${why}`)
  }
  for (const s of open) console.log(`  ${s.id}  ${s.role}  still running (excluded from ship unless --include-open)`)
  if (unclaimed.length) console.log(`Dirty files no session claims: ${unclaimed.length} (included only with ship --all)`)
  if (info.ahead) console.log(`${info.ahead} commit(s) not pushed.`)
}

function cmdTail(id, lines = 80) {
  if (!id) die('usage: tail <session-id> [lines]')
  const s = loadSessions().find(x => x.id === id)
  if (!s) die(`no session ${id}`)
  const file = path.join(SESSIONS_DIR, s.id, s.transcript ?? 'transcript.log')
  if (!fs.existsSync(file)) die('transcript not found (it is kept locally and never committed)')
  const text = fs.readFileSync(file, 'utf8').split('\n')
  console.log(text.slice(-Number(lines)).join('\n'))
}

function parseArgs(argv) {
  const o = { trailers: [] }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    const next = () => argv[++i] ?? die(`${a} needs a value`)
    if (a === '--sessions') o.sessions = next().split(',').map(x => x.trim()).filter(Boolean)
    else if (a === '--all') o.all = true
    else if (a === '--include-open') o.includeOpen = true
    else if (a === '--message') o.message = next()
    else if (a === '--trailer') o.trailers.push(next())
    else if (a === '--note') o.note = next()
    else if (a === '--push') o.push = true
    else if (a === '--dry-run') o.dryRun = true
    else if (a === '--allow-prestaged') o.allowPrestaged = true
    else die(`unknown option ${a}`)
  }
  return o
}

function stamp(d = new Date()) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
}

function cmdShip(argv) {
  const o = parseArgs(argv)
  const all = loadSessions()
  let pool = all.filter(s => !DONE.has(stateOf(s)))
  if (o.sessions) {
    const unknown = o.sessions.filter(id => !all.some(s => s.id === id))
    if (unknown.length) die(`unknown session(s): ${unknown.join(', ')}`)
    const done = o.sessions.filter(id => DONE.has(stateOf(all.find(s => s.id === id))))
    if (done.length) console.log(`note: already packaged, ignoring: ${done.join(', ')}`)
    pool = pool.filter(s => o.sessions.includes(s.id))
  }
  const deferredOpen = pool.filter(s => !s.endedAt && !o.includeOpen)
  const included = pool.filter(s => s.endedAt || o.includeOpen)
  const notSelected = o.sessions ? all.filter(s => !DONE.has(stateOf(s)) && !o.sessions.includes(s.id)) : []

  const info = branchInfo()
  const dirty = dirtyNow()
  const claimed = new Set(included.flatMap(s => (s.uncommittedFiles ?? []).map(f => f.path)))
  let wanted = o.all ? dirty : dirty.filter(d => claimed.has(d.path))
  const sensitive = wanted.filter(d => SENSITIVE.test(d.path))
  wanted = wanted.filter(d => !SENSITIVE.test(d.path))
  const leftBehind = dirty.filter(d => !wanted.includes(d) && !sensitive.includes(d))

  if (!included.length && !wanted.length) {
    console.log('Nothing to ship: no ended sessions waiting and no matching dirty files.')
    if (deferredOpen.length) console.log(`Still running: ${deferredOpen.map(s => s.id).join(', ')}`)
    return
  }

  // Refuse to sweep unrelated, already-staged work into this commit.
  const staged = git(['diff', '--cached', '--name-only', '-z']).split('\0').filter(Boolean)
    .filter(p => !p.startsWith(`${SESSIONS_REL}/`))
  const foreign = staged.filter(p => !wanted.some(w => w.path === p))
  if (foreign.length && !o.allowPrestaged) {
    die(`${foreign.length} file(s) are already staged and not part of this package (${foreign.slice(0, 5).join(', ')}${foreign.length > 5 ? ', ...' : ''}). Unstage them or pass --allow-prestaged.`)
  }

  const packageId = `P-${stamp()}`
  const roles = [...new Set(included.map(s => s.role))]
  const subject = o.message ?? `Package ${included.length} session${included.length === 1 ? '' : 's'}${roles.length ? ` (${roles.join(', ')})` : ''} [${packageId}]`
  const body = [
    ...included.map(s => `- ${s.id} ${s.role}: ${s.uncommittedFiles?.length ?? 0} file(s), ended by ${s.endReason ?? 'running'}`),
    ...(sensitive.length ? ['', `Skipped ${sensitive.length} sensitive-looking file(s).`] : []),
  ].join('\n')

  const pkgRel = `${SESSIONS_REL}/packages/${packageId}.md`
  const pkgAbs = path.join(ROOT, pkgRel)
  const pkg = renderPackage({ packageId, o, info, included, deferredOpen, notSelected, wanted, sensitive, leftBehind, subject })

  console.log(`Branch: ${info.branch}${info.upstream ? ` -> ${info.upstream}` : ' (no upstream; push would create one on origin)'}`)
  console.log(`Sessions: ${included.length} included, ${deferredOpen.length} still running, ${notSelected.length} not selected`)
  console.log(`Files to commit: ${wanted.length}${wanted.length ? '\n' + wanted.map(w => `  ${w.xy.trim().padEnd(2)} ${w.path}`).join('\n') : ''}`)
  if (sensitive.length) console.log(`Skipped as sensitive-looking: ${sensitive.map(s => s.path).join(', ')}`)
  if (leftBehind.length) console.log(`Left uncommitted: ${leftBehind.length} file(s) not claimed by the included sessions${o.all ? '' : ' (use --all to include)'}`)
  console.log(`Commit: ${subject}`)
  if (o.dryRun) return console.log('\nDry run: nothing was written, staged or committed.')

  const priorOutcomes = new Map()
  const touched = [...included, ...deferredOpen, ...notSelected]
  for (const s of touched) priorOutcomes.set(s.id, s.outcome)
  const rollback = () => {
    for (const s of touched) { s.outcome = priorOutcomes.get(s.id); saveSession(s) }
    try { fs.rmSync(pkgAbs, { force: true }) } catch { /* ignore */ }
  }

  // Record outcomes before the commit so the commit itself contains them.
  const when = new Date().toISOString()
  for (const s of included) {
    const files = s.uncommittedFiles ?? []
    const committedCount = files.filter(f => wanted.some(w => w.path === f.path)).length
    if (!files.length) {
      s.outcome = { state: 'nothing-to-commit', reason: s.commitsDuringSession?.length ? 'work was already committed during the session' : 'session changed no files', packageId, at: when }
    } else if (!committedCount) {
      s.outcome = { state: 'skipped', reason: 'its files were no longer changed or were skipped as sensitive', packageId, at: when }
    } else {
      s.outcome = { state: 'committed', packageId, at: when }
    }
  }
  for (const s of deferredOpen) s.outcome = { state: 'deferred', reason: 'pane still running when packaged', packageId, at: when }
  for (const s of notSelected) s.outcome = { state: s.outcome?.state ?? 'unpackaged', ...(s.outcome ?? {}), reason: 'not selected for this package', packageId, at: when }
  for (const s of touched) saveSession(s)
  fs.mkdirSync(path.dirname(pkgAbs), { recursive: true })
  fs.writeFileSync(pkgAbs, pkg)

  const msgFile = path.join(os.tmpdir(), `aiterminal-commit-${packageId}.txt`)
  fs.writeFileSync(msgFile, [subject, '', body, ...(o.trailers.length ? ['', ...o.trailers] : [])].join('\n') + '\n')
  try {
    for (const group of chunked(wanted.map(w => w.path))) git(['add', '-A', '--', ...group])
    git(['add', '-A', '--', SESSIONS_REL])
    git(['commit', '-F', msgFile])
  } catch (err) {
    try { git(['reset', '-q']) } catch { /* ignore */ }
    rollback()
    const detail = (err.stderr || err.stdout || err.message || '').toString().trim()
    console.error(`Commit failed; sessions stay uncommitted and nothing was left staged.\n${detail}`)
    for (const s of included) { s.outcome = { state: 'failed', reason: 'commit failed: ' + detail.split('\n')[0].slice(0, 160), at: when }; saveSession(s) }
    process.exit(1)
  } finally { fs.rmSync(msgFile, { force: true }) }

  const sha = git(['rev-parse', '--short', 'HEAD']).trim()
  console.log(`\nCommitted ${sha}: ${subject}`)
  console.log(`Package log: ${pkgRel}`)

  if (o.push) {
    try {
      const args = info.upstream ? ['push'] : ['push', '-u', 'origin', info.branch]
      const out = execFileSync('git', ['-C', ROOT, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
      console.log(`Pushed ${info.branch}. ${out.trim()}`)
    } catch (err) {
      const detail = (err.stderr || err.message || '').toString().trim()
      console.error(`Push failed (the commit is safe locally):\n${detail}`)
      process.exit(2)
    }
  } else {
    console.log('Not pushed (pass --push to push).')
  }
}

function renderPackage({ packageId, o, info, included, deferredOpen, notSelected, wanted, sensitive, leftBehind, subject }) {
  const L = []
  L.push(`# Package ${packageId}`, '')
  L.push(`- created: ${new Date().toISOString()}`)
  L.push(`- branch: ${info.branch}`)
  L.push(`- commit subject: ${subject}`)
  L.push(`- commit: the commit that adds this file (\`git log -- ${SESSIONS_REL}/packages/${packageId}.md\`)`)
  if (o.note) L.push(`- note: ${o.note}`)
  L.push('', '## Sessions included', '')
  if (!included.length) L.push('None.')
  for (const s of included) {
    L.push(`### ${s.id} (${s.role})`)
    L.push(`- ${fmt(s.startedAt)} to ${fmt(s.endedAt)} (${duration(s)}), ended by ${s.endReason ?? 'running'}`)
    if (s.endReason === 'crashed') L.push('- the app closed unexpectedly; end-of-session file list was reconstructed at next launch')
    if (s.commitsDuringSession?.length) L.push(`- commits made during the session: ${s.commitsDuringSession.map(c => `${c.sha.slice(0, 7)} ${c.subject}`).join('; ')}`)
    const files = s.uncommittedFiles ?? []
    L.push(files.length ? `- files left uncommitted by the session (${files.length}):` : '- no uncommitted files')
    for (const f of files) L.push(`  - ${f.path}${wanted.some(w => w.path === f.path) ? '' : '  (not committed: no longer changed or skipped)'}`)
    L.push('')
  }
  L.push('## Not committed, and why', '')
  const why = []
  for (const s of deferredOpen) why.push(`- session ${s.id} (${s.role}): pane still running; try again after it ends`)
  for (const s of notSelected) why.push(`- session ${s.id} (${s.role}): ended but not selected for this package`)
  for (const f of sensitive) why.push(`- ${f.path}: looks sensitive (credentials or key material); stage it by hand if intended`)
  for (const f of leftBehind) why.push(`- ${f.path}: dirty but not claimed by an included session${o.all ? '' : '; use --all to include'}`)
  L.push(why.length ? why.join('\n') : 'Nothing was left out.')
  L.push('', `Raw terminal transcripts stay on this machine in ${SESSIONS_REL}/<session-id>/transcript.log and are never committed.`, '')
  return L.join('\n')
}

// ── main ─────────────────────────────────────────────────────────────────────

const [cmd, ...rest] = process.argv.slice(2)
switch (cmd) {
  case 'status': cmdStatus(); break
  case 'list': cmdList(); break
  case 'tail': cmdTail(rest[0], rest[1]); break
  case 'ship': cmdShip(rest); break
  default:
    console.log('usage: node agents/sessions/sessions.mjs <status | list | tail <id> [lines] | ship [options]>\nSee the header of this file or agents/sessions/README.md.')
    process.exit(cmd ? 1 : 0)
}
