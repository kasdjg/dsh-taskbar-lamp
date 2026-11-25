import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const SCRIPT = path.join(here, 'lamp', 'app.py')

function pickPython(config) {
  const candidates = [
    config && config.pythonPath,
    process.env.DSH_LAMP_PYTHON,
    'D:\\develop\\python313\\pythonw.exe',
    'C:\\Python313\\pythonw.exe',
  ].filter(Boolean)
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate
  }
  return 'pythonw'
}

function log(ctx, level, message) {
  try {
    const logger = ctx.logger ? ctx.logger('taskbar-lamp') : null
    if (logger && typeof logger[level] === 'function') logger[level](message)
  } catch {
    // logging must never break the lamp
  }
}

export function apply(ctx, config) {
  if (process.platform !== 'win32') {
    log(ctx, 'info', 'taskbar lamp is Windows-only; skipped on this platform')
    return
  }

  const settings = config || {}
  const python = pickPython(settings)
  let child = null
  let startedAt = 0

  const start = () => {
    if (child && child.exitCode === null) return
    startedAt = Date.now()
    try {
      child = spawn(python, [SCRIPT], {
        cwd: here,
        windowsHide: true,
        stdio: 'ignore',
        detached: false,
      })
      child.on('error', (err) => {
        log(ctx, 'warn', `cannot start taskbar lamp with "${python}": ${err.message}`)
        child = null
      })
      child.on('exit', (code) => {
        const lived = Date.now() - startedAt
        if (lived < 3000) {
          log(ctx, 'warn', `taskbar lamp exited early (code ${code}); check Python plus Pillow, pystray and zstandard`)
        }
        child = null
      })
    } catch (err) {
      log(ctx, 'warn', `taskbar lamp failed to spawn: ${err.message}`)
      child = null
    }
  }

  ctx.effect(() => {
    start()
    return () => {
      const running = child
      child = null
      if (running && running.exitCode === null) {
        try {
          running.kill()
        } catch {
          // already gone
        }
      }
    }
  })
}
