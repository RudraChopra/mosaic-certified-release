from __future__ import annotations

from summarize_mosaic_bridge_evidence import aggregate, aggregate_cell, paired_contrasts


def row(
    rule: str,
    dataset: str,
    seed: int,
    *,
    deployed: bool,
    estimable: bool,
    false_acceptance: bool,
) -> dict[str, object]:
    return {
        "rule": rule,
        "dataset": dataset,
        "seed": seed,
        "utility_threshold": "0.40",
        "deployed": deployed,
        "diagnostic_estimable": estimable,
        "false_acceptance": false_acceptance,
        "candidate": "A" if deployed else None,
        "method": "LEACE" if deployed else None,
    }


def test_cell_uses_estimable_deployments_as_false_acceptance_denominator() -> None:
    summary = aggregate_cell(
        [
            row("strict_mosaic", "D", 1, deployed=True, estimable=True, false_acceptance=False),
            row("strict_mosaic", "D", 2, deployed=True, estimable=False, false_acceptance=False),
            row("strict_mosaic", "D", 3, deployed=True, estimable=True, false_acceptance=True),
            row("strict_mosaic", "D", 4, deployed=False, estimable=False, false_acceptance=False),
        ]
    )
    assert summary["deployments"] == 3
    assert summary["estimable_deployments"] == 2
    assert summary["unestimable_deployments"] == 1
    assert summary["false_acceptances"] == 1
    assert summary["false_acceptance_rate_among_estimable"] == 0.5


def test_aggregate_and_paired_contrast_keep_all_rules() -> None:
    rows = [
        row("strict_mosaic", "D", 1, deployed=True, estimable=True, false_acceptance=False),
        row("strict_mosaic", "D", 2, deployed=False, estimable=False, false_acceptance=False),
        row("capacity_transfer", "D", 1, deployed=False, estimable=False, false_acceptance=False),
        row("capacity_transfer", "D", 2, deployed=True, estimable=True, false_acceptance=False),
    ]
    # Add empty comparison rows so the contrast function receives its full schema.
    for rule_name in (
        "bridge_plugin",
        "validation_plugin",
        "always_deploy_validation",
    ):
        rows.extend(
            row(rule_name, "D", seed, deployed=False, estimable=False, false_acceptance=False)
            for seed in (1, 2)
        )
    cells = aggregate(rows, ["D"], ["0.40"])
    assert cells["strict_mosaic"]["D"]["0.40"]["deployments"] == 1
    contrast = paired_contrasts(rows, ["0.40"])["capacity_transfer"]["0.40"]
    assert contrast["mosaic_only_deployments"] == 1
    assert contrast["comparator_only_deployments"] == 1
    assert contrast["paired_deployment_difference"] == 0.0
