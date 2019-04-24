import os

from tox.venv import VirtualEnv
from tox_conda.plugin import tox_testenv_create, tox_testenv_install_deps


def test_conda_create(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
    """,
    )

    venv = VirtualEnv(config.envconfigs["py123"])
    assert venv.path == config.envconfigs["py123"].envdir

    with mocksession.newaction(venv.name, "getenv") as action:
        tox_testenv_create(action=action, venv=venv)
    pcalls = mocksession._pcalls
    assert len(pcalls) >= 1
    call = pcalls[-1]
    assert "conda" in call.args[0]
    assert "create" == call.args[1]
    assert "--yes" == call.args[2]
    assert "--override-channels" == call.args[3]
    assert "-p" == call.args[4]
    assert venv.path == call.args[5]
    assert "--channel=defaults" == call.args[6]
    assert call.args[7].startswith("python=")


def create_test_env(config, mocksession, envname):

    venv = VirtualEnv(config.envconfigs[envname])
    with mocksession.newaction(venv.name, "getenv") as action:
        tox_testenv_create(action=action, venv=venv)
    pcalls = mocksession._pcalls
    assert len(pcalls) >= 1
    pcalls[:] = []

    return venv, action, pcalls


def test_install_deps_no_conda(newconfig, mocksession):
    """Test installation using conda when no conda_deps are given"""
    config = newconfig(
        [],
        """
        [testenv:py123]
        deps=
            numpy
            astropy
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert len(venv.envconfig.deps) == 2
    assert len(venv.envconfig.conda_deps) == 0

    tox_testenv_install_deps(action=action, venv=venv)
    assert len(pcalls) >= 1
    call = pcalls[-1]
    cmd = call.args
    assert cmd[1:4] == ["-m", "pip", "install"]


def test_install_conda_deps(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
        deps=
            numpy
            astropy
        conda_deps=
            pytest
            asdf
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert len(venv.envconfig.conda_deps) == 2
    assert len(venv.envconfig.deps) == 2 + len(venv.envconfig.conda_deps)

    tox_testenv_install_deps(action=action, venv=venv)
    # We expect two calls: one for conda deps, and one for pip deps
    assert len(pcalls) >= 2
    call = pcalls[-2]
    conda_cmd = call.args
    assert "conda" in os.path.split(conda_cmd[0])[-1]
    assert conda_cmd[1:6] == ["install", "--yes", "--override-channels", "-p", venv.path]
    assert conda_cmd[6] == "--channel=defaults"
    # Make sure that python is explicitly given as part of every conda install
    # in order to avoid inadvertant upgrades of python itself.
    assert conda_cmd[7].startswith("python=")
    assert conda_cmd[8:10] == ["pytest", "asdf"]

    pip_cmd = pcalls[-1].args
    assert pip_cmd[1:4] == ["-m", "pip", "install"]
    assert pip_cmd[4:6] == ["numpy", "astropy"]


def test_install_conda_no_pip(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
        conda_deps=
            pytest
            asdf
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert len(venv.envconfig.conda_deps) == 2
    assert len(venv.envconfig.deps) == len(venv.envconfig.conda_deps)

    tox_testenv_install_deps(action=action, venv=venv)
    # We expect only one call since there are no true pip dependencies
    assert len(pcalls) >= 1

    # Just a quick sanity check for the conda install command
    call = pcalls[-1]
    conda_cmd = call.args
    assert "conda" in os.path.split(conda_cmd[0])[-1]
    assert conda_cmd[1:6] == ["install", "--yes", "--override-channels", "-p", venv.path]


def test_install_conda_no_channels(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
        conda_deps=
            pytest
            asdf
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert venv.envconfig.conda_channels == []

    tox_testenv_install_deps(action=action, venv=venv)
    assert len(pcalls) >= 1
    call = pcalls[-1]
    conda_cmd = call.args
    assert "conda" in os.path.split(conda_cmd[0])[-1]
    assert "--override-channels" in conda_cmd
    assert "--channel=defaults" in conda_cmd


def test_install_conda_channels(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
        conda_channels=
            conda-forge
        conda_deps=
            pytest
            asdf
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert venv.envconfig.conda_channels == ["conda-forge"]

    tox_testenv_install_deps(action=action, venv=venv)
    assert len(pcalls) >= 1
    call = pcalls[-1]
    conda_cmd = call.args
    assert "conda" in os.path.split(conda_cmd[0])[-1]
    assert "--override-channels" in conda_cmd
    channels = [arg for arg in conda_cmd if arg.startswith("--channel")]
    assert len(channels) == 1
    assert "--channel=conda-forge" in channels


def test_update(tmpdir, newconfig, mocksession):
    pkg = tmpdir.ensure("package.tar.gz")
    config = newconfig(
        [],
        """
        [testenv:py123]
        deps=
            numpy
            astropy
        conda_deps=
            pytest
            asdf
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")
    tox_testenv_install_deps(action=action, venv=venv)

    venv.hook.tox_testenv_create = tox_testenv_create
    venv.hook.tox_testenv_install_deps = tox_testenv_install_deps
    with mocksession.newaction(venv.name, "update") as action:
        venv.update(action)
        venv.installpkg(pkg, action)
