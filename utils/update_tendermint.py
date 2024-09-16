#!/usr/bin/env python3
import time
import json
import requests

with open("../api_ids/coingecko_ids.json", "r") as f:
    repo_gecko_ids = json.load(f)
with open("../api_ids/binance_ids.json", "r") as f:
    repo_binance_ids = json.load(f)
with open("../api_ids/livecoinwatch_ids.json", "r") as f:
    repo_livecoinwatch_ids = json.load(f)


def get_gecko_info(id):
    url = "https://pro-api.coingecko.com/api/v3/coins/{id}"
    headers = {"accept": "application/json"}
    return requests.get(url, headers=headers).json()


def get_cosmos_directory():
    url = "https://chains.cosmos.directory"
    return requests.get(url).json()["chains"]


def get_cosmos_chain(chain_registry_name):
    try:
        url = f"https://chains.cosmos.directory/{chain_registry_name}/chain"
        return requests.get(url).json()
    except:
        print(f"Error getting chain data for {chain_registry_name}: {url}")
        return None


def get_cosmos_assets(chain_registry_name):
    try:
        url = f"https://chains.cosmos.directory/{chain_registry_name}/assetlist"
        return requests.get(url).json()["assets"]
    except:
        print(f"Error getting assets data for {chain_registry_name}: {url}")
        return None


def get_new_coins():
    cosmos_chains = get_cosmos_directory()
    print(f"Found {len(cosmos_chains)} Cosmos chains")

    new_coins_data = []
    new_explorers = {}
    new_images = {}
    dead = []
    for i in cosmos_chains:
        time.sleep(0.1)
        if i["status"] != "live":
            print(f"{i['symbol']} is {i['status']}!")
            dead.append(i["symbol"])
            continue
        # Using defaults for some values for now
        avg_blocktime = 7
        mm2 = 1
        wallet_only = True
        main_symbol = i["symbol"]
        print(f"Processing {main_symbol} ({i['name']})")
        chain_id = i["chain_id"]
        if "slip44" not in i:
            print(f"Skipping {main_symbol} because it has no slip44")
            continue
        derivation_path = f"m/44'/{i['slip44']}'"
        chain_registry_name = i["name"]
        fname = i["pretty_name"]
        account_prefix = i["bech32_prefix"]
        # TODO: backfill from existing repo data for other price ids
        if "coingecko_id" not in i:
            gecko_id = ""
            gecko_info = None
        else:
            gecko_id = i["coingecko_id"]
            gecko_info = get_gecko_info(gecko_id)

        # Proxies to best available
        nodes = {
            "url": "https://rpc.cosmos.directory/{chain_registry_name}",
            "api_url": "https://rest.cosmos.directory/{chain_registry_name}",
        }

        # TODO: make explorer files for each chain
        if "explorers" in i:
            new_explorers.update({main_symbol: i["explorers"]})

        chain_data = get_cosmos_chain(chain_registry_name)
        if chain_data is None:
            print(f"Skipping {chain_registry_name} because there is no chain data")
            continue
        if "explorers" in chain_data:
            new_explorers.update({main_symbol: chain_data["explorers"]})
        if "images" in chain_data:
            if len(chain_data["images"]) > 0:
                if "png" in chain_data["images"][0]:
                    new_images.update({main_symbol: chain_data["images"][0]["png"]})

        if "coingecko_id" not in chain_data:
            print(f"{main_symbol} has no coingecko_id!")
            gecko_id = ""
            gecko_info = None
        elif gecko_id == "":
            gecko_id = chain_data["coingecko_id"]
            gecko_info = get_gecko_info(gecko_id)

        assets_data = get_cosmos_assets(chain_registry_name)
        if assets_data is None:
            print(f"Skipping {chain_registry_name} because there is no assets data")
            continue
        for j in assets_data:
            if j["symbol"] == main_symbol:
                base_denom = j["base"]
                if len(j["denom_units"]) > 2:
                    print(f"Skipping {main_symbol} because it has more than 2 denom units")
                    continue
                for k in j["denom_units"]:
                    if k["exponent"] != 0:
                        decimals = k["exponent"]
                        break
            if "fees" not in chain_data:
                continue
            if "fee_tokens" not in chain_data["fees"]:
                continue
            if len(chain_data["fees"]["fee_tokens"]) == 0:
                continue
            if "average_gas_price" not in chain_data["fees"]["fee_tokens"][0]:
                continue
            gas_price = chain_data["fees"]["fee_tokens"][0]["average_gas_price"]

        try:
            new_coins_data.append(
                {
                    "coin": main_symbol,
                    "avg_blocktime": avg_blocktime,
                    "name": chain_registry_name,
                    "fname": fname,
                    "mm2": mm2,
                    "wallet_only": wallet_only,
                    "protocol": {
                        "type": "TENDERMINT",
                        "protocol_data": {
                            "decimals": decimals,
                            "denom": base_denom,
                            "account_prefix": account_prefix,
                            "chain_registry_name": chain_registry_name,
                            "chain_id": chain_id,
                            "gas_price": gas_price,
                        },
                    },
                    "derivation_path": derivation_path,
                }
            )
        except Exception as e:
            print(f"Error adding for {main_symbol} to new_coins_data: {e}")
            continue

        for j in assets_data:
            symbol = j["symbol"]
            ticker = f"{symbol}-IBC_{main_symbol}"
            denom = j["base"]
            if symbol in dead:
                print(f"Skipping {ticker} because {symbol} is dead")
                continue

            if symbol == main_symbol:
                continue
            if "type_asset" not in j:
                print(f"Skipping {ticker} because it has no type_asset")
                continue
            if j["type_asset"] != "ics20":
                print(
                    f"Skipping {ticker} because it is not an IBC asset: {j['type_asset']}"
                )
                continue

            print(f"Processing {ticker} ({j['name']})")
            try:
                if "coingecko_id" not in j:
                    gecko_id = ""
                    gecko_info = None
                else:
                    gecko_id = j["coingecko_id"]
                    gecko_info = get_gecko_info(gecko_id)
                if j["symbol"] == main_symbol:
                    print(f"Skipping {ticker} because you cant be a token of yourself")
                    continue

                new_coins_data.append(
                    {
                        "coin": ticker,
                        "name": ticker.lower(),
                        "fname": j["name"],
                        "avg_blocktime": avg_blocktime,
                        "mm2": mm2,
                        "wallet_only": wallet_only,
                        "protocol": {
                            "type": "TENDERMINTTOKEN",
                            "protocol_data": {
                                "platform": main_symbol,
                                "decimals": decimals,
                                "denom": denom,
                                "gas_price": gas_price,
                            },
                        },
                    }
                )
            except Exception as e:
                print(f"Error adding for {ticker} to new_coins_data: {e}")
                continue

    with open("new_tendermint_coins.json", "w") as f:
        json.dump(new_coins_data, f, indent=4)

    print(f"Found {len(new_coins_data)} new coins")
    return new_coins_data, new_explorers, new_images

def update_repo_data():
    with open("../coins", "r") as f:
        verify = []
        updated_coins = []
        coins = json.load(f)
        coins_list = [i['coin'] for i in coins]
        new_coins, new_explorers, new_images = get_new_coins()
        new_coins_list = [i['coin'] for i in new_coins]
        for i in coins:
            # Retain existing coins not in the update
            if i['coin'] not in new_coins_list:
                updated_coins.append(i)
        for j in new_coins:
            updated_coins.append(j)
            if j['coin'] in coins_list:
                print(f"{j['coin']} update is replacing exisiting data, please verify!")
                verify.append(j)
                # TODO: automate comparison of data
        with open("updated_coins", "w") as f:
            json.dump(updated_coins, f, indent=4)
        print(f"Updated {len(updated_coins)} coins")
        print(f"{len(verify)} coins to verify: {verify}")

if __name__ == "__main__":
    update_repo_data()
                