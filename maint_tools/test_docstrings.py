import re
from inspect import signature
from typing import Optional

import pytest
from sklearn.utils._testing import all_estimators

numpydoc_validation = pytest.importorskip("numpydoc.validate")

# List of whitelisted modules and methods; regexp are supported.
DOCSTRING_WHITELIST = [
    "LogisticRegression$",
    "LogisticRegression.fit",
    "LogisticRegression.decision_function",
    "Birch.predict",
    "Birch.transform",
    "LinearDiscriminantAnalysis.decision_function",
    "LinearSVC.decision_function",
    "LogisticRegressionCV.decision_function",
    "PassiveAggressiveClassifier.decision_function",
    "Perceptron.decision_function",
    "RidgeClassifier.decision_function",
    "RidgeClassifierCV.decision_function",
    "SGDClassifier.decision_function",
]


def get_all_methods():
    estimators = all_estimators()
    for name, estimator in estimators:
        if name.startswith("_"):
            # skip private classes
            continue
        methods = [el for el in dir(estimator) if not el.startswith("_")]
        methods.append(None)

        for method in sorted(methods, key=lambda x: str(x)):
            yield estimator, method


def filter_errors(errors, method):
    """
    Ignore some errors based on the method type.

    These rules are specific for scikit-learn."""
    for code, message in errors:
        # We ignore following error code,
        #  - RT02: The first line of the Returns section
        #    should contain only the type, ..
        #   (as we may need refer to the name of the returned
        #    object)
        #  - GL01: Docstring text (summary) should start in the line
        #  immediately after the opening quotes (not in the same line,
        #  or leaving a blank line in between)

        if code in ["RT02", "GL01"]:
            continue

        # Following codes are only taken into account for the
        # top level class docstrings:
        #  - ES01: No extended summary found
        #  - SA01: See Also section not found
        #  - EX01: No examples section found

        if method is not None and code in ["EX01", "SA01", "ES01"]:
            continue
        yield code, message


def repr_errors(res, estimator=None, method: Optional[str] = None) -> str:
    """Pretty print original docstring and the obtained errors

    Parameters
    ----------
    res : dict
        result of numpydoc.validate.validate
    estimator : {estimator, None}
        estimator object or None
    method : str
        if estimator is not None, either the method name or None.

    Returns
    -------
    str
       String representation of the error.
    """
    if method is None:
        if hasattr(estimator, "__init__"):
            method = "__init__"
        elif estimator is None:
            raise ValueError(
                "At least one of estimator, method should be provided"
            )
        else:
            raise NotImplementedError

    if estimator is not None:
        obj_signature = signature(getattr(estimator, method))
        obj_name = estimator.__name__ + "." + method
    else:
        obj_signature = ""
        obj_name = method

    msg = "\n\n" + "\n\n".join(
        [
            res["file"],
            obj_name + str(obj_signature),
            res["docstring"],
            "# Errors",
            "\n".join(
                " - {}: {}".format(code, message)
                for code, message in res["errors"]
            ),
        ]
    )
    return msg


@pytest.mark.parametrize("estimator, method", get_all_methods())
def test_docstring(estimator, method, request):
    base_import_path = estimator.__module__
    import_path = [base_import_path, estimator.__name__]
    if method is not None:
        import_path.append(method)

    import_path = ".".join(import_path)

    if not any(re.search(regex, import_path) for regex in DOCSTRING_WHITELIST):
        request.applymarker(
            pytest.mark.xfail(
                run=False, reason="TODO pass numpydoc validation"
            )
        )

    res = numpydoc_validation.validate(import_path)

    res["errors"] = list(filter_errors(res["errors"], method))

    if res["errors"]:
        msg = repr_errors(res, estimator, method)

        raise ValueError(msg)


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate docstring with numpydoc."
    )
    parser.add_argument("import_path", help="Import path to validate")

    args = parser.parse_args()

    res = numpydoc_validation.validate(args.import_path)

    import_path_sections = args.import_path.split(".")
    # When applied to classes, detect class method. For functions
    # method = None.
    # TODO: this detection can be improved. Currently we assume that we have
    # class # methods if the second path element before last is in camel case.
    if len(import_path_sections) >= 2 and re.match(
        r"(?:[A-Z][a-z]*)+", import_path_sections[-2]
    ):
        method = import_path_sections[-1]
    else:
        method = None

    res["errors"] = list(filter_errors(res["errors"], method))

    if res["errors"]:
        msg = repr_errors(res, method=args.import_path)

        print(msg)
        sys.exit(1)
    else:
        print("All docstring checks passed for {}!".format(args.import_path))
