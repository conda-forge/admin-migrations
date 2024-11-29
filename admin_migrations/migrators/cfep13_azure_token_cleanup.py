from .base import Migrator


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


class CFEP13AzureTokenCleanup(Migrator):
    main_branch_only = True
    max_workers = 1
    max_migrate = 200

    def migrate(self, feedstock, branch):
        user = "conda-forge"
        project = "%s-feedstock" % feedstock

        if branch == "master" or branch == "main":
            # remove BINSTAR_TOKEN and STAGING_BINSTAR_TOKEN from azure
            # this removes the tokens attached to the specific pipeline, not the org
            _delete_tokens_in_azure(
                user,
                project,
                ["BINSTAR_TOKEN", "STAGING_BINSTAR_TOKEN"],
            )
            print(
                "    deleted BINSTAR_TOKEN and STAGING_BINSTAR_TOKEN from azure",
                flush=True,
            )

        # migration done, make a commit, lots of API calls
        return True, False, True
