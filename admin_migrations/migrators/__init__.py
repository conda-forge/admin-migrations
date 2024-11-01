# flake8: noqa
from .automerge_and_rerender import AutomergeAndRerender
from .automerge_and_botrerun_labels import AutomergeAndBotRerunLabels
from .appveyor_cleanup import AppveyorDelete, AppveyorForceDelete
from .r_automerge import RAutomerge
from .cfep13_tokens_and_config import CFEP13TokensAndConfig, CFEP13TurnOff
from .conda_forge_automerge import CondaForgeAutomerge, CondaForgeAutomergeUpdate
from .teams_cleanup import TeamsCleanup
from .cfep13_token_cleanup import CFEP13TokenCleanup
from .travis_auto_cancel_prs import TravisCIAutoCancelPRs
from .cfep13_azure_token_cleanup import CFEP13AzureTokenCleanup
from .rotate_feedstock_tokens import RotateFeedstockToken
from .rotate_cf_staging_token import RotateCFStagingToken
from .main_default_branch import CondaForgeGHAWithMain, CondaForgeMasterToMain
from .travis_cleanup_osx_amd64 import TraviCINoOSXAMD64
from .feedstocks_service_update import FeedstocksServiceUpdate
from .dot_conda import DotConda
from .conda_forge_yml_test import CondaForgeYAMLTest
from .branch_protection import BranchProtection
from .remove_automerge_and_rerender import RemoveAutomergeAndRerender
