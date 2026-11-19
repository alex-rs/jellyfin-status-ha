# AGENTS.md

## Git remotes
- **Always push to both remotes**: GitHub (`origin`) and the self-hosted Forgejo mirror (`forgejo`). `origin` has both as push URLs, so a plain `git push` / `git push origin <branch>` sends to both.
- Check that both pushes succeeded. If one fails, fix it and push again, so `main`/`master` is always identical on GitHub and Forgejo.
