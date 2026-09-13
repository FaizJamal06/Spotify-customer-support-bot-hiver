"""
Evaluation metrics for the intent-classification baselines, computed against
golden_set/GOLDEN_200_FINAL.csv (the only evaluation set used here).
"""
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
)


def compute_metrics(y_true, y_pred, labels):
    """
    labels: the fixed, ordered list of the 8 frozen intents (config.FROZEN_LABELS) --
            fixes row/column order in per-class results and the confusion matrix
            regardless of which labels happen to appear in y_true/y_pred.
    Returns a JSON-serializable dict.
    """
    accuracy = accuracy_score(y_true, y_pred)

    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )

    per_class_p, per_class_r, per_class_f1, per_class_support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average=None, zero_division=0
    )
    per_class = {
        label: dict(
            precision=float(per_class_p[i]),
            recall=float(per_class_r[i]),
            f1=float(per_class_f1[i]),
            support=int(per_class_support[i]),
        )
        for i, label in enumerate(labels)
    }

    cm = confusion_matrix(y_true, y_pred, labels=labels)

    return dict(
        accuracy=float(accuracy),
        macro_precision=float(macro_p),
        macro_recall=float(macro_r),
        macro_f1=float(macro_f1),
        per_class=per_class,
        confusion_matrix=dict(
            labels=list(labels),
            matrix=cm.tolist(),  # rows = true label, columns = predicted label
        ),
        n_examples=len(y_true),
    )
