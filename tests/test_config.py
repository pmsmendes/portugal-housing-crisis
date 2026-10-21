from pthousing import config


def test_project_dirs_exist():
    for path in (config.RAW, config.EXTERNAL, config.INTERIM, config.PROCESSED, config.CONFIG):
        assert path.is_dir(), path


def test_phase_output_dirs_exist():
    for phase in config.PHASES:
        assert (config.FIGURES / phase).is_dir()
        assert (config.TABLES / phase).is_dir()
