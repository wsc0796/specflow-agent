"""Local entry point; preparing the dataset never launches a provider."""

from specflow.evaluation.dev_baseline import main

if __name__ == "__main__":
    raise SystemExit(main())
