# Contributing to 4DPocket

Thank you for considering contributing to 4DPocket! This guide will help you get started.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/4DPocket.git
   cd 4DPocket
   ```
3. Follow the [Development Guide](DEVELOPMENT.md) to set up your local environment

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the conventions below

3. Run checks before committing:
   ```bash
   make lint        # Linting
   make test        # Tests
   cd frontend && pnpm build  # Frontend type check
   ```

4. Commit with a conventional commit message:
   ```
   feat: add new platform processor for Bluesky
   fix: handle empty response in Reddit processor
   refactor: simplify AI provider selection logic
   docs: update configuration reference
   test: add tests for share permissions
   chore: update dependencies
   perf: optimize FTS5 search query
   ```

5. Push and open a Pull Request against `main`

## Code Conventions

### Backend (Python)

- **Python 3.12+** with type hints
- **Sync route handlers** — use `def`, not `async def` (SQLModel is sync)
- **Ruff** for linting and formatting (`make lint`, `make format`)
- **No passlib, python-jose, axios, or litellm** — see CLAUDE.md for rationale
- **Auth**: PyJWT + bcrypt direct
- **HTTP client**: httpx (not requests)
- **AI safety**: Always sanitize user content via `ai/sanitizer.py` before LLM prompts
- **User scoping**: Every DB query must include `WHERE user_id = current_user.id`
- **Config**: Use `FDP_` prefixed environment variables via pydantic-settings

### Frontend (TypeScript/React)

- **React 19** with functional components and hooks
- **TanStack Query** for server state, **Zustand** for client state
- **Tailwind CSS v4** for styling
- **Lucide React** for icons (not other icon libraries)
- **Native fetch** via `api/client.ts` wrapper (not axios)
- **Dark mode**: Use Tailwind `dark:` variants

### File Organization

- Keep files under 400 lines (800 max)
- One component per file
- Organize by feature/domain, not by type

## Adding a Platform Processor

1. Create `src/fourdpocket/processors/your_platform.py`
2. Extend `BaseProcessor` and use `@register_processor` decorator
3. Define URL patterns in `url_patterns`
4. Implement `process(url)` returning a `ProcessorResult`
5. Add SSRF-safe fetching via `self._fetch_url()` (never use `follow_redirects=True`)

```python
@register_processor
class BlueSkyProcessor(BaseProcessor):
    name = "bluesky"
    url_patterns = [r"https?://bsky\.app/profile/.+/post/.+"]

    def process(self, url: str) -> ProcessorResult:
        response = self._fetch_url(url)
        # ... extract content ...
        return ProcessorResult(status=ProcessorStatus.SUCCESS, ...)
```

## Testing

- Write tests in `tests/`
- Use `pytest` fixtures for DB sessions
- Mock external HTTP calls with `respx`
- Run: `make test` or `uv run pytest tests/ -x -q`
- Coverage: `make test-cov`

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- 4DPocket version (`v0.1.0`, etc.)
- Deployment method (Docker, source, pip)

## Feature Requests

Open an issue with:
- Use case description
- Proposed solution (if any)
- Whether you're willing to implement it

## Code of Conduct

Be respectful, constructive, and inclusive. We're all here to build something useful together.

## License

By contributing, you agree that your contributions will be licensed under the GNU GPLv3 License.
