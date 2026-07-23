import run_mosaic_large_release_scaling as study


def test_locked_design_has_21_jobs_and_large_alphabets():
    jobs = sum(
        len(released_counts) * len(study.SEEDS)
        for released_counts in study.POINTS.values()
    )
    assert jobs == 21
    assert 8 in study.POINTS[4]
    assert 16 in study.POINTS[2]


def test_balanced_decoder_has_declared_length():
    for released_count in (2, 4, 8, 16):
        decoder = tuple(
            [0] * (released_count // 2) + [1] * (released_count // 2)
        )
        assert len(decoder) == released_count
        assert sum(decoder) == released_count // 2
