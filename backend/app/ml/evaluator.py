import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class FailureRiskEvaluator:

    def evaluate(
        self,
        y_true: pd.Series,
        y_pred: pd.Series,
        y_proba: pd.Series | None = None,
    ) -> dict:

        if len(y_true) == 0:
            raise ValueError(
                "y_true must not be empty"
            )

        if len(y_true) != len(y_pred):
            raise ValueError(
                "y_true and y_pred must have the same number of rows"
            )

        if y_proba is not None and len(y_true) != len(y_proba):
            raise ValueError(
                "y_true and y_proba must have the same number of rows"
            )

        tn, fp, fn, tp = confusion_matrix(
            y_true,
            y_pred,
            labels=[0, 1],
        ).ravel()

        metrics = {
            "accuracy": float(
                accuracy_score(
                    y_true,
                    y_pred,
                )
            ),
            "precision": float(
                precision_score(
                    y_true,
                    y_pred,
                    zero_division=0,
                )
            ),
            "recall": float(
                recall_score(
                    y_true,
                    y_pred,
                    zero_division=0,
                )
            ),
            "f1": float(
                f1_score(
                    y_true,
                    y_pred,
                    zero_division=0,
                )
            ),
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        }

        if (
            y_proba is not None
            and y_true.nunique() == 2
        ):
            metrics["roc_auc"] = float(
                roc_auc_score(
                    y_true,
                    y_proba,
                )
            )
        else:
            metrics["roc_auc"] = None

        return metrics