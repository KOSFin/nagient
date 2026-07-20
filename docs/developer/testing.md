# Developer: Testing Plugins

Language: English | [Русский](testing.ru.md)

Every plugin repository should run tests before publishing a tag.

## Python plugin

Use the repository's own virtual environment and keep the core as a test
dependency:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests
```

At minimum test manifest parsing, invalid configuration, secret references,
normalization of one inbound event, and a mocked outbound request. Do not call
Telegram, GitHub, or an LLM from unit tests.

## Process plugin

Test the JSON protocol with fixture requests:

```bash
printf '%s\n' '{"protocol":"nagient.process.v1","method":"healthcheck"}' | ./plugin
```

The process must return one JSON object and never write logs to stdout; use
stderr for diagnostics.

## Release checklist

1. Pin dependencies and run the test suite on Python 3.11 and 3.12.
2. Run `nagient plugin install <repo>#<tag>` in a clean runtime.
3. Run `nagient preflight --format json` and inspect errors.
4. Add the repository and its tag to the official catalog only after review.
