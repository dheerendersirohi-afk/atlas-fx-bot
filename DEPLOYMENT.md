# Deployment

## Free hosting

This project's local dashboard is a static site in `web/`, so the cleanest free hosting option is GitHub Pages.

## GitHub Pages setup

1. Push this repository to GitHub.
2. Make sure your default branch is `main`.
3. In the GitHub repository, open `Settings` > `Pages`.
4. Set the source to `GitHub Actions`.
5. Push to `main` or manually run the workflow in `.github/workflows/github-pages.yml`.

GitHub Pages will publish the contents of the `web/` folder through the workflow.

## Important limit

The hosted site is still only the static dashboard and paper bot.

It does not magically enable:

- live broker credentials
- real MT4/MT5 terminal execution
- OANDA live trading
- broker deposits or withdrawals

Those parts still need a backend, broker credentials, and runtime access outside static hosting.
