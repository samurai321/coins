#!/usr/bin/env python3
import os
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

def validate_symbol(symbol):
    if symbol.upper() != symbol:
        print(f"Skipping {symbol} because it is not all uppercase")
        return False
    if symbol.find(' ') > -1:
        print(f"Skipping {symbol} because it has a space in it")
        return False
    if symbol.find('.') > -1:
        print(f"Skipping {symbol} because it has a '.' in it")
        return False
    if symbol.find('-') > -1:
        print(f"Skipping {symbol} because it has a '-' in it")
        return False
    return True


def get_new_coins():
    cosmos_chains = get_cosmos_directory()
    print(f"Found {len(cosmos_chains)} Cosmos chains")

    new_coins_data = []
    new_explorers = {}
    new_images = {}
    new_gecko_ids = {}
    fnames = {}
    dead = []
    with open("../coins", "r") as f:
        old_coins = json.load(f)

    # Get coin fullnames to standardise on IBC assets
    for i in cosmos_chains:
        fnames.update({i["symbol"]: i["pretty_name"]})
    for i in old_coins:
        fnames.update({i["coin"]: i["fname"]})
        
    for i in cosmos_chains:
        main_symbol = i["symbol"]
        time.sleep(0.1)
        if i["status"] != "live":
            print(f"{main_symbol} is {i['status']}!")
            dead.append(main_symbol)
            continue
        if "slip44" not in i:
            print(f"Skipping {main_symbol} because it has no slip44")
            continue
        if validate_symbol(main_symbol) is False:
            continue

        print(f"Processing {main_symbol} ({i['name']})")
        # Using defaults for some values for now
        avg_blocktime = 7
        mm2 = 1
        wallet_only = True
        chain_id = i["chain_id"]
        derivation_path = f"m/44'/{i['slip44']}'"
        chain_registry_name = i["name"]
        fname = i["pretty_name"]
        account_prefix = i["bech32_prefix"]
        # TODO: backfill from existing repo data for other price ids
        if "coingecko_id" not in i:
            gecko_id = ""
        else:
            gecko_id = i["coingecko_id"]

        chain_data = get_cosmos_chain(chain_registry_name)
        if chain_data is None:
            print(f"Skipping {chain_registry_name} because there is no chain data")
            continue

        if "fees" not in chain_data:
            continue
        if "fee_tokens" not in chain_data["fees"]:
            continue
        if len(chain_data["fees"]["fee_tokens"]) == 0:
            continue
        if "average_gas_price" not in chain_data["fees"]["fee_tokens"][0]:
            continue
        gas_price = chain_data["fees"]["fee_tokens"][0]["average_gas_price"]
        
        if "coingecko_id" not in chain_data:
            print(f"{main_symbol} has no coingecko_id!")
            gecko_id = ""
        elif gecko_id == "":
            gecko_id = chain_data["coingecko_id"]

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
            if "explorers" in i:
                new_explorers.update({main_symbol: [e['url'] for e in i["explorers"]]})
            if "explorers" in chain_data:
                new_explorers.update({main_symbol: [e['url'] for e in chain_data["explorers"]]})
            if "images" in chain_data:
                if len(chain_data["images"]) > 0:
                    if "png" in chain_data["images"][0]:
                        new_images.update({main_symbol: chain_data["images"][0]["png"]})
            new_gecko_ids.update({main_symbol: gecko_id})
        except Exception as e:
            print(f"Error adding for {main_symbol} to new_coins_data: {e}")
            continue

        for j in assets_data:
            symbol = j["symbol"]
            if validate_symbol(symbol) is False:
                continue
            if symbol in dead:
                print(f"Skipping {ticker} because {symbol} is dead")
                continue
            ticker = f"{symbol}-IBC_{main_symbol}"
            denom = j["base"]

            if symbol == main_symbol:
                if symbol not in new_images:
                    if "images" in j:
                        if len(j["images"]) > 0:
                            if "png" in j["images"][0]:
                                new_images.update({symbol: j["images"][0]["png"]})
                continue
            if "type_asset" not in j:
                print(f"Skipping {ticker} because it has no type_asset")
                continue
            if j["type_asset"] != "ics20":
                print(
                    f"Skipping {ticker} because it is not an IBC asset: {j['type_asset']}"
                )
                continue

            print(f"Processing {ticker} ({fname})")
            try:
                if "coingecko_id" not in j:
                    gecko_id = ""
                    # gecko_info = None
                else:
                    gecko_id = j["coingecko_id"]
                    # gecko_info = get_gecko_info(gecko_id)
                if j["symbol"] == main_symbol:
                    print(f"Skipping {ticker} because you cant be a token of yourself")
                    continue
                if symbol in fnames:
                    fullname = fnames[symbol]
                else:
                    fullname = j['name']
                
                new_coins_data.append(
                    {
                        "coin": ticker,
                        "name": ticker.lower(),
                        "fname": fullname,
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
                new_gecko_ids.update({ticker: gecko_id})
                if symbol not in new_images:
                    if "images" in j:
                        if len(j["images"]) > 0:
                            if "png" in j["images"][0]:
                                new_images.update({symbol: j["images"][0]["png"]})
                
            except Exception as e:
                print(f"Error adding for {ticker} to new_coins_data: {e}")
                continue

    with open("new_tendermint_coins.json", "w") as f:
        new_coins_data = sorted(new_coins_data, key=lambda x: x['coin'])
        json.dump(new_coins_data, f, indent=4)

    print(f"Found {len(new_coins_data)} new coins")
    return new_coins_data, new_explorers, new_images, new_gecko_ids


def is_tendermint_coin(coin_data):
    try:
        if coin_data['protocol']['type'] == "TENDERMINT":
            return True
    except:
        pass
    return False


def update_repo_data():
    # `coins` file update
    with open("../coins", "r") as f:
        verify = []
        updated_coins = []
        coins = json.load(f)
        coins_list = [i['coin'] for i in coins]
        new_coins, new_explorers, new_images, new_gecko_ids = get_new_coins()
        new_coins_list = [i['coin'] for i in new_coins]
        for i in coins:
            # Retain existing coins not in the update
            if i['coin'] not in new_coins_list:
                updated_coins.append(i)
        for j in new_coins:
            updated_coins.append(j)
            if j['coin'] in coins_list:
                print(f"{j['coin']} update is replacing exisiting data, please verify!")
                verify.append(j['coin'])
                # TODO: automate comparison of data
        with open("updated_coins", "w") as f:
            json.dump(updated_coins, f, indent=4)
        print(f"Updated {len(updated_coins)} coins")
        print(f"{len(verify)} coins to verify: {verify}")
        print(f"Once verified, replace `coins` with `updated_coins`")
        # TODO: automate comparison of data, ignore where no changes


    # `tendermint` folder update
    tendermint_servers = os.listdir("../tendermint")
    for i in updated_coins:
        if is_tendermint_coin(i):
            servers = {"rpc_nodes": []}
            skip_update = False
            if 'chain_registry_name' in i['protocol']['protocol_data']:
                chain_registry_name = i['protocol']['protocol_data']['chain_registry_name']

                if i['coin'] in tendermint_servers:
                    with open(f"../tendermint/{i['coin']}", "r") as f:
                        servers = json.load(f)
                        for server in servers['rpc_nodes']:
                            if server['url'] == f"https://rpc.cosmos.directory/{chain_registry_name}":
                                skip_update = True
                if i['coin'] in ["IRISTEST", "NUCLEUSTEST"]:
                    skip_update = True
                if skip_update is False:
                    # Proxies to best available
                    proxy_nodes = {
                        "url": f"https://rpc.cosmos.directory/{chain_registry_name}",
                        "api_url": f"https://rest.cosmos.directory/{chain_registry_name}"
                    }
                    print(f"Updating {i['coin']} with proxy nodes")
                    print(servers)
                    servers['rpc_nodes'].append(proxy_nodes)
                    servers['rpc_nodes'].sort(key=lambda x: x['url'])
                    with open(f"../tendermint/{i['coin']}", "w+") as f:
                        json.dump(servers, f, indent=4)
                        print(f"Updated {i['coin']} with proxy nodes")

    # `explorers` folder update
    old_explorers = os.listdir("../explorers")
    for i in updated_coins:
        if is_tendermint_coin(i):
            explorers = []
            if i['coin'] in old_explorers:
                with open(f"../explorers/{i['coin']}", "r") as f:
                    explorers = json.load(f)

            if i['coin'] in new_explorers:
                
                explorers = sorted(list(set(explorers + new_explorers[i['coin']])))
                with open(f"../explorers/{i['coin']}", "w+") as f:
                    json.dump(explorers, f, indent=4)
                    print(f"Updated {i['coin']} with explorer nodes")

    # `api_ids` folder update
    with open("../api_ids/coingecko_ids.json", "r") as f:
        old_gecko_ids = json.load(f)
        
    for i in new_gecko_ids:
        if new_gecko_ids[i] == "":
            base_coin = i.split('-')[0]
            if base_coin in old_gecko_ids:
                old_gecko_ids.update({
                    i: old_gecko_ids[base_coin]
                })
        else:
            old_gecko_ids.update({i: new_gecko_ids[i]})
    with open("../api_ids/coingecko_ids.json", "w") as f:
        json.dump(old_gecko_ids, f, indent=4)
            
    # `images` folder update
    for i in new_images:
        if i not in os.listdir("../icons_original"):
            os.system(f"wget {new_images[i]} -O ../icons_original/{i.lower()}.png")
            print(f"Downloaded {i}.png")
        else:
            print(f"Skipping {i}.png because it already exists")
        
    

if __name__ == "__main__":
    update_repo_data()
                