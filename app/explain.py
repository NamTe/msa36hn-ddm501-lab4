"""
SHAP explanations for individual scoring decisions.

"""

import logging
from typing import Any, Dict, List

import numpy as np

from pipeline.preprocessing import add_derived_features

logger = logging.getLogger(__name__)


class Explainer:
    """Wraps a SHAP TreeExplainer around the fitted pipeline.

    The pipeline is (features -> classifier). SHAP needs the raw estimator and
    the TRANSFORMED matrix, so this class holds both halves and does the
    transformation itself. Handing the whole pipeline to shap and hoping is
    the usual mistake.
    """

    def __init__(self, pipeline: Any):
        self.pipeline = pipeline
        self.feature_step = pipeline.named_steps["features"]
        self.classifier = pipeline.named_steps["classifier"]
        self.feature_names = list(
            self.feature_step.named_steps["preprocess"].get_feature_names_out()
        )
        self._explainer = None

    def _ensure_explainer(self):
        """Build the explainer on first use.

        Lazily, because importing shap costs about a second and a container
        that is not asked for explanations should not pay it at startup.
        """
        if self._explainer is None:
            import shap

            self._explainer = shap.TreeExplainer(self.classifier)
        return self._explainer

    def explain(self, frame, top_n: int = 8) -> Dict[str, Any]:
        """Return the features that moved this one score, largest first.

        TASK 10:
          - Transform the frame with self.feature_step, then call
            shap_values on self.classifier's explainer.
          - Depending on the model, shap returns (n, features) or
            (n, features, classes). Normalise to the positive class.
          - expected_value may be a scalar or an array; normalise it too.
          - Sort by ABSOLUTE contribution and keep the top n.
          - Report the applicant's OWN value for each feature, not the
            standardised one. add_derived_features(frame) gives you the
            derived ones; one-hot columns have no counterpart in the
            application and fall back to the transformed value. An adverse
            action notice quoting "your PAY_0 was 2.16" cannot be reconciled
            with the application form by anyone outside the ML team.
        """
        transformed = self.feature_step.transform(frame)
        explainer = self._ensure_explainer()
        shap_values = explainer.shap_values(transformed)
        if isinstance(shap_values, list):
            shap_values = shap_values[1 if len(shap_values) > 1 else 0]
        shap_values = np.asarray(shap_values)
        if shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1 if shap_values.shape[2] > 1 else 0]
        contributions = shap_values[0]

        expected = np.asarray(explainer.expected_value).reshape(-1)
        base_value = float(expected[1 if expected.size > 1 else 0])
        original = add_derived_features(frame).iloc[0]
        indices = np.argsort(-np.abs(contributions))[:max(0, top_n)]
        result: List[Dict[str, Any]] = []
        for index in indices:
            name = self.feature_names[index]
            value = original[name] if name in original.index else transformed[0, index]
            contribution = float(contributions[index])
            result.append(
                {
                    "feature": name,
                    "value": float(value),
                    "contribution": contribution,
                    "direction": "increases risk" if contribution > 0 else "reduces risk",
                }
            )
        return {"base_value": base_value, "contributions": result}
