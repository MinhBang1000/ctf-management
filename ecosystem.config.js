// PM2 process definitions for HSLab CTF Classroom.
//
// 3 processes (PRD §3.6, updated for Phase 3's Celery scheduler), all
// prefixed "hslab-" so they never collide with other PM2 processes
// already running on this machine (§3.6 req #5).
// NEVER run pm2 stop/delete/restart/kill with "all" or no name — always
// target these processes by their exact name. See README.md.
module.exports = {
  apps: [
    {
      name: "hslab-app",
      script: "./scripts/start-app.sh",
      interpreter: "bash",
      cwd: __dirname,
      out_file: "./logs/hslab-app-out.log",
      error_file: "./logs/hslab-app-error.log",
      autorestart: true,
      max_restarts: 20,
      restart_delay: 2000,
    },
    {
      name: "hslab-tunnel",
      script: "./scripts/start-tunnel.sh",
      interpreter: "bash",
      cwd: __dirname,
      // Combined stdout+stderr on purpose: cloudflared prints the Quick
      // Tunnel URL on stderr, and scripts/get-tunnel-url.sh greps this
      // single file for it.
      out_file: "./logs/hslab-tunnel.log",
      error_file: "./logs/hslab-tunnel.log",
      autorestart: true,
      max_restarts: 20,
      restart_delay: 2000,
    },
    {
      name: "hslab-celery",
      script: "./scripts/start-celery.sh",
      interpreter: "bash",
      cwd: __dirname,
      out_file: "./logs/hslab-celery-out.log",
      error_file: "./logs/hslab-celery-error.log",
      autorestart: true,
      max_restarts: 20,
      restart_delay: 2000,
    },
  ],
};
