# ==============================================================================
# MAKRAY — Windows PowerShell helper (for users without `make`)
# ==============================================================================
# Usage:  .\make.ps1 <command>
# Example: .\make.ps1 setup
#          .\make.ps1 test
#          .\make.ps1 doctor
#
# This is a thin wrapper around npm scripts so Windows users can run the same
# commands as Makefile users without installing GNU make.
# ==============================================================================

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host ""
    Write-Host "MAKRAY - available commands" -ForegroundColor Cyan
    Write-Host "============================" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Setup"
    Write-Host "    setup              First-time setup (install + .env)"
    Write-Host "    install            Install dependencies"
    Write-Host "    env                Create .env from template"
    Write-Host ""
    Write-Host "  Development"
    Write-Host "    dev                Start development server (Phase 3+)"
    Write-Host "    build              Compile TypeScript"
    Write-Host "    typecheck          Type-check without output"
    Write-Host "    clean              Remove build artifacts"
    Write-Host "    clean-all          Remove everything including node_modules"
    Write-Host ""
    Write-Host "  Testing"
    Write-Host "    test               Run full test suite"
    Write-Host "    test-watch         Run tests in watch mode"
    Write-Host "    test-coverage      Run with coverage report"
    Write-Host ""
    Write-Host "  Database (Phase 1+)"
    Write-Host "    db-migrate         Run pending migrations"
    Write-Host "    db-reset           Reset database"
    Write-Host "    db-seed            Seed development data"
    Write-Host ""
    Write-Host "  Deployment"
    Write-Host "    deploy-staging     Deploy to staging"
    Write-Host "    deploy-prod        Deploy to production"
    Write-Host ""
    Write-Host "  Meta"
    Write-Host "    check              typecheck + test"
    Write-Host "    doctor             Diagnose environment"
    Write-Host "    help               Show this message"
    Write-Host ""
    Write-Host "Platform detected: Windows" -ForegroundColor DarkGray
    Write-Host ""
}

switch ($Command.ToLower()) {
    "help"             { Show-Help }
    "setup"            { npm install; npm run env; Write-Host "`n✓ Setup complete. Next: edit .env, then .\make.ps1 dev" -ForegroundColor Green }
    "install"          { npm install }
    "env"              { npm run env }

    "dev"              { npm run dev }
    "build"            { npm run build }
    "typecheck"        { npm run typecheck }
    "lint"             { npm run lint }
    "format"           { npm run format }
    "clean"            { npm run clean }
    "clean-all"        { npm run "clean:all" }

    "test"             { npm test -- --runInBand }
    "test-watch"       { npm run "test:watch" }
    "test-coverage"    { npm run "test:coverage" }
    "test-integration" { npm run "test:integration" }

    "db-migrate"       { npm run "db:migrate" }
    "db-reset"         { npm run "db:reset" }
    "db-seed"          { npm run "db:seed" }

    "deploy-staging"   { npm test -- --runInBand; npm run typecheck; npm run "deploy:staging" }
    "deploy-prod"      {
        npm test -- --runInBand
        npm run typecheck
        $confirm = Read-Host "Deploy to PRODUCTION? [y/N]"
        if ($confirm -eq "y") { npm run "deploy:prod" } else { Write-Host "Aborted." -ForegroundColor Yellow }
    }

    "check"            { npm run check }
    "doctor"           { npm run doctor }
    "version"          { npm run "version:print" }

    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host "Run '.\make.ps1 help' to see available commands." -ForegroundColor DarkGray
        exit 1
    }
}
