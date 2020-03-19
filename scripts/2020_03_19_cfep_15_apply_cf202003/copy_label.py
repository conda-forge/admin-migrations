from binstar_client.utils import get_server_api

print("executing the copy")
a = get_server_api()
a.copy_channel("main", "conda-forge", "cf202003")
