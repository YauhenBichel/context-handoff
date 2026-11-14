# Contributing

Thanks for helping.

- Open an issue first for anything bigger than a small fix.
- Work on a branch and open a pull request against `main`. CI must be green.
- Keep the package free of third-party dependencies: it runs as a hook on
  every prompt, with only the Python standard library.
- Add or change a test in `tests/` for every behaviour you change, and run
  `python3 -m unittest discover -s tests` before pushing.
- Hooks must never break a session: on any error they print nothing and exit 0.
- Price changes: link the official pricing page in the pull request.
