import os
import subprocess

import requests
from ruamel.yaml import YAML

from .base import Migrator


def _delete_token_in_circle(user, project, token_name):
    from conda_smithy.ci_register import circle_token

    url_template = (
        "https://circleci.com/api/v1.1/project/github/{user}/{project}/envvar{extra}?"
        "circle-token={token}"
    )

    r = requests.get(
        url_template.format(token=circle_token, user=user, project=project, extra="")
    )
    if r.status_code != 200:
        r.raise_for_status()

    have_binstar_token = False
    for evar in r.json():
        if evar["name"] == token_name:
            have_binstar_token = True

    if have_binstar_token:
        r = requests.delete(
            url_template.format(
                token=circle_token,
                user=user,
                project=project,
                extra="/%s" % token_name,
            )
        )
        if r.status_code != 200:
            r.raise_for_status()


def _delete_token_in_drone(user, project, token_name):
    from conda_smithy.ci_register import drone_session

    session = drone_session()

    r = session.get(f"/api/repos/{user}/{project}/secrets")
    r.raise_for_status()
    have_binstar_token = False
    for secret in r.json():
        if token_name == secret["name"]:
            have_binstar_token = True

    if have_binstar_token:
        r = session.delete(f"/api/repos/{user}/{project}/secrets/{token_name}")
        r.raise_for_status()


def _delete_tokens_in_azure(user, project, token_names):
    from conda_smithy.azure_ci_utils import build_client, get_default_build_definition
    from conda_smithy.azure_ci_utils import default_config as config

    bclient = build_client()

    existing_definitions = bclient.get_definitions(
        project=config.project_name, name=project
    )
    if existing_definitions:
        assert len(existing_definitions) == 1
        ed = existing_definitions[0]
    else:
        raise RuntimeError(
            "Cannot delete tokens %s from a repo that is not already "
            "registerd on azure CI!" % token_names
        )

    ed = bclient.get_definition(ed.id, project=config.project_name)

    if not hasattr(ed, "variables") or ed.variables is None:
        variables = {}
    else:
        variables = ed.variables

    for token_name in token_names:
        if token_name in variables:
            del variables[token_name]

    build_definition = get_default_build_definition(
        user,
        project,
        config=config,
        variables=variables,
        id=ed.id,
        revision=ed.revision,
    )

    bclient.update_definition(
        definition=build_definition,
        definition_id=ed.id,
        project=ed.project.name,
    )


def _delete_token_in_travis(user, project, token_name):
    """update the binstar token in travis."""
    from conda_smithy.ci_register import (
        travis_endpoint,
        travis_get_repo_info,
        travis_headers,
    )

    headers = travis_headers()

    repo_info = travis_get_repo_info(user, project)
    repo_id = repo_info["id"]

    r = requests.get(
        f"{travis_endpoint}/repo/{repo_id}/env_vars",
        headers=headers,
    )
    if r.status_code != 200:
        r.raise_for_status()

    have_binstar_token = False
    ev_id = None
    for ev in r.json()["env_vars"]:
        if ev["name"] == token_name:
            have_binstar_token = True
            ev_id = ev["id"]

    if have_binstar_token:
        r = requests.delete(
            f"{travis_endpoint}/repo/{repo_id}/env_var/{ev_id}",
            headers=headers,
        )
        r.raise_for_status()


def _read_conda_forge_yaml(yaml):
    if os.path.exists("conda-forge.yml"):
        with open("conda-forge.yml") as fp:
            meta_yaml = fp.read()

        if (
            meta_yaml is None
            or meta_yaml.strip() == "[]"
            or meta_yaml.strip() == "[ ]"
            or len(meta_yaml) == 0
            or len(meta_yaml.strip()) == 0
        ):
            cfg = {}
        else:
            cfg = yaml.load(meta_yaml)
    else:
        meta_yaml = ""
        cfg = {}

    return cfg


def _cleanup_cfgy(code, top, token_name):
    if top in code and "secure" in code[top] and token_name in code[top]["secure"]:
        del code[top]["secure"][token_name]

        if len(code[top]["secure"]) == 0:
            del code[top]["secure"]

        if len(code[top]) == 0:
            del code[top]

        return True
    else:
        return False


class CFEP13TokenCleanup(Migrator):
    max_workers = 1
    max_migrate = 200

    def migrate(self, feedstock, branch):
        user = "conda-forge"
        project = "%s-feedstock" % feedstock

        if branch == "master" or branch == "main":
            # these two token changes are not needed anymore
            # staged-recipes does this by default now
            # put the staging token into BINSTAR_TOKEN
            # subprocess.run(
            #     "conda smithy update-binstar-token "
            #     "--without-appveyor --without-azure "
            #     "--token_name BINSTAR_TOKEN",
            #     shell=True,
            #     check=True
            # )
            # print("    putting cf-staging binstar token in BINSTAR_TOKEN", flush=True)

            # put the staging token into STAGING_BINSTAR_TOKEN
            # subprocess.run(
            #     "conda smithy update-binstar-token "
            #     "--without-appveyor --without-azure "
            #     "--token_name STAGING_BINSTAR_TOKEN",
            #     shell=True,
            #     check=True
            # )
            # print(
            #     "    putting cf-staging binstar token "
            #     "in STAGING_BINSTAR_TOKEN",
            #     flush=True
            # )

            # needs a change in smithy so cannot do this
            # # remove STAGING_BINSTAR_TOKEN from travis, circle and drone
            # _delete_token_in_circle(user, project, "STAGING_BINSTAR_TOKEN")
            # print("    deleted STAGING_BINSTAR_TOKEN from circle", flush=True)
            #
            # _delete_token_in_drone(user, project, "STAGING_BINSTAR_TOKEN")
            # print("    deleted STAGING_BINSTAR_TOKEN from drone", flush=True)
            #
            # _delete_token_in_travis(user, project, "STAGING_BINSTAR_TOKEN")
            # print("    deleted STAGING_BINSTAR_TOKEN from travis", flush=True)

            # remove BINSTAR_TOKEN and STAGING_BINSTAR_TOKEN from azure
            # this removes the tokens attached to the specific pipeline, not the org
            # we should move this bit of code to staged recipes and then turn this off
            _delete_tokens_in_azure(
                user,
                project,
                ["BINSTAR_TOKEN", "STAGING_BINSTAR_TOKEN"],
            )
            print(
                "    deleted BINSTAR_TOKEN and STAGING_BINSTAR_TOKEN from azure",
                flush=True,
            )

        # cleanup conda-forge.yml
        yaml = YAML()
        cfg = _read_conda_forge_yaml(yaml)
        _cleanup_cfgy(cfg, "travis", "BINSTAR_TOKEN")
        _cleanup_cfgy(cfg, "appveyor", "BINSTAR_TOKEN")
        with open("conda-forge.yml", "w") as fp:
            yaml.dump(cfg, fp)
        subprocess.run(
            ["git", "add", "conda-forge.yml"],
            check=True,
        )
        print("    updated conda-forge.yml", flush=True)

        # migration done, make a commit, lots of API calls
        return True, True, True
