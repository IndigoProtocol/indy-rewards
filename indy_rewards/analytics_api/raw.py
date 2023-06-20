"""Indigo analytics API presented as-is, with documentation."""

from typing import Optional

import requests

BASE_URL = "https://analytics.indigoprotocol.io/api"
TIMEOUT = 20  # Seconds.


def asset_prices(at_unix_time: Optional[float]) -> list[dict]:
    """On-chain oracle feeds' latest state.

    Args:
        at_unix_time: Unix time for which we'd like the latest price oracle data.
            Can be any past time to get historical prices. None to get current prices.

    Returns:
        List of dicts, each entry is an on-chain oracle price announcement.

        Dict structure:

        hash (str): SHA-256 hash of the string {output_hash}#{output_index}.{asset}
            for newer entries (without the curly braces).
            For older entries it's the hash of {output_hash}#{output_index}, without
            the asset name part.
        slot (int): Cardano global slot number of the block the transaction is in.
        output_hash (str): Tx hash of the price update tx.
        output_index (int): Index of the tx output which contains the price datum.
        asset (str): Name of the iAsset as a hex string.
        price (int): One iAsset unit's on-chain price in ADA lovelaces.
        expiration (int): Unix time in milliseconds at which this price becomes invalid.
        address (str): Bech32 address of the off-chain bot wallet that posted the
            price on-chain.
        created_at (str): Database entry creation timestamp.
        updated_at (str): Database entry last update timestamp.

    Examples:
        >>> prices = asset_prices(1671905105)  # 2022 December 24 18:05:05 UTC.
        >>> len(prices)
        2
        >>> [x["asset"] for x in prices]
        ['iUSD', 'iBTC']
        >>> prices[0]
        {'hash': '3e9e81d0abef6a8651bda17fb255492cac898dca4e711b8d0be7e5304c8d1983',
         'slot': 80336651,
         'output_hash': 'b165baba1b483f1421295cda6ccbde6db7ebbb77d3d444f98479dc40693f6b68',
         'output_index': 0,
         'asset': 'iUSD',
         'price': 3855050,
         'expiration': 1671905903000,
         'address': 'addr1wygyy4mdrh5kxsmm6ja4phxez3vh2mngz2muqmw4gw3n9jqdu67a0',
         'created_at': '2022-12-24T17:29:02.000000Z',
         'updated_at': '2022-12-24T17:29:02.000000Z'}
    """
    url = BASE_URL + "/asset-prices"
    if at_unix_time is None:
        response = requests.get(url, timeout=TIMEOUT)
    else:
        response = requests.post(url, json={"timestamp": at_unix_time}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def cdps(at_unix_time: Optional[float]) -> list[dict]:
    """State of all open CDPs at a given time.

    Args:
        at_unix_time: Unix time for which we'd like the latest CDP data.
            Can be any past time to get historical prices.
            None to get current open CDPs.

    Returns:
        List of dicts, each representing an open (at the time) CDP. Dict structure:

        output_hash (str): Tx hash of the last transaction of the open CDP.
        output_index (int): Index of the tx output where the CDP token representing the
            account was sent.
        owner (str): The special account identifier PaymentKeyHash of the CDP's owner,
            in hex format.
        asset (str): Name of the iAsset.
        collateralAmount (int): ADA collateral backing the CDP, in lovelaces.
        mintedAmount (int): iAsset debt of the CDP, in iAsset "lovelaces" (i.e. *1M).

    Examples:
        >>> cdp_list = cdps(1675082096)  # 2023 January 30 12:34:56 UTC.
        >>> len(cdp_list)
        943
        >>> cdp_list[99]
        {'output_hash': '88009f09a041da8eaeb78c34c6391587c4d055f3fc7f565576d73feb608719e4',
         'output_index': 1,
         'owner': '67b9e1699f39f1483dbe59aaca3fe0689992c2c0c996d6394e4f7569',
         'asset': 'iUSD',
         'collateralAmount': 100000000,
         'mintedAmount': 12408722}
    """
    url = BASE_URL + "/cdps"
    if at_unix_time is None:
        response = requests.get(url, timeout=TIMEOUT)
    else:
        response = requests.post(url, json={"timestamp": at_unix_time}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def liquidity_pools():
    """Dex liquidity pool attributes of pools whitelisted on Indigo for INDY LP rewards.

    Returns:
        List of dicts, each representing a liquidity pool. Dict structure:

        token: Liquidity pool token's policy ID (this tends to be the same for a lot
            of pools within a dex) and the LP token's name (this is different for each
            pool within a given dex), concatenated with a "." separator.
        assetA (str): Pair's first asset's name. Typically the iAsset.
        assetB (str): Pair's second asset's name. Typically ADA.
        exchange (str): Name of the dex.
        assetALogo (str): Path to the A asset's logo file relative to the Indigo web app
            root URL.
        assetBLogo (str): Path of the B asset's logo in the web app.
        exchangeLogo (str): Path of the exchange's logo in the web app.

    Examples:
        >>> len(liquidity_pools())
        8
        >>> liquidity_pools()[0]
        {'token': '026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570.63a3b8ee322ea31a931fd1902528809dc681bc650af21895533c9e98fa4bef2e',
         'assetA': 'iBTC',
         'assetB': 'ADA',
         'exchange': 'WingRiders',
         'assetALogo': '/assets/images/assets/iBTC.png',
         'assetBLogo': '/assets/images/cardano-logo.png',
         'exchangeLogo': '/assets/images/exchanges/wingriders.png'}
    """
    response = requests.get(BASE_URL + "/liquidity-pools", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def liquidity_pools_locked_asset(
    after_unix_time: Optional[float],
    dex_script_address: Optional[str] = None,
    asset_id: Optional[str] = None,
    description: Optional[str] = None,
) -> list[dict]:
    """Dex liquidity pool iAsset balance snapshots.

    Note that unlike the name of the API endpoint might suggest, the returned iAsset
    amounts aren't iAssets locked into Indigo. They're simply iAsset balances of
    liquidity pools.

    NOTE: It also returns some unrelated entries that aren't iAsset balances, but
    WingRiders LP token balances of select addresses. These can be separated from
    normal entries based on their "lp_token" property being an empty string, and that
    their "for" property ends in " Token Locked". You'll probably want to filter these
    out.

    In practice mostly daily snapshots taken around 21:46 UTC are returned by the API.

    So if you want to find out dex balances around 21:45 UTC on a given day, you can use
    the date + 21:45 in the "after_unix_time" filter and discard entries from the reply
    that are for more recent days.

    Args:
        after_unix_time: Filters outputs, only those with a "timestamp" greater than or
            equal to after_unix_time will be returned. If None, all snapshots ever will
            be returned.
        dex_script_address: Filter for the "address" output field (see below).
        asset_id: Filter for "asset".
        description: Filter for the "for" field.

    Returns:
        List of dicts, each a snapshot of a dex liquidity pool's iAsset balance at a
        given time, with a bunch of redundant info included.

        NOTE: Returns unrelated special LP balances too, see note above.

        The dicts in the list are ordered descending by "timestamp", newest are first.

        Dict structure:

        id (int): Database primary key.
        for (str): Human readable description of the entry.
        address (str): Bech32 address of the dex smart contract holding the funds.
        asset (str): Policy ID and name of the iAsset, both in hex format, concatted
            with a "." separator.
        lp_token (str): Policy ID and name of the LP token, both in hex, concatted with
            a "." separator. Corresponds to liquidity_pools() reply's "token" field.
        amount (int): iAsset held by the liquidity pool, in iAsset lovelaces
            (i.e. multiplied by a million).
        timestamp (int): Unix time of the snapshot, in seconds (not millis).
        created_at (str): Database entry creation timestamp.
        updated_at (str): Database entry last update timestamp.

    Examples:
        >>> lp_snaps = liquidity_pools_locked_asset(1680385500)  # 2023 April 1 21:45 UTC
        >>> len(lp_snaps)
        264
        >>> lp_snaps[-1]
        {'id': 722,
         'for': 'WingRiders iETH/ADA iETH Locked',
         'address': 'addr1z8nvjzjeydcn4atcd93aac8allvrpjn7pjr2qsweukpnay0pm0c29jpny4jh6z7vlz0l7v0u7037rz43xm29yc85744sc4mmph',
         'asset': 'f66d78b4a3cb3d37afa0ec36461e51ecbde00f26c8f0a68f94b69880.69455448',
         'lp_token': '026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570.562b9ff903fe8d9e1c980120a233051e7b1518cfc75eb9b4227f7710b670b6e9',
         'amount': 190293062,
         'timestamp': 1680385561,
         'created_at': '2023-04-01T21:46:01.000000Z',
         'updated_at': '2023-04-01T21:46:01.000000Z'}
         >>> len(liquidity_pools_locked_asset(1680385500, description="WingRiders iETH/ADA iETH Locked"))
         33
    """
    params: dict[str, float | str] = {}
    if after_unix_time is not None:
        params["after"] = after_unix_time
    if dex_script_address is not None:
        params["address"] = dex_script_address
    if asset_id is not None:
        params["asset"] = asset_id
    if description is not None:
        params["for"] = description
    response = requests.get(
        BASE_URL + "/liquidity-pools/locked-asset", params=params, timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def liquidity_pools_circulating_supply(
    after_unix_time: Optional[float],
    asset_id: Optional[str] = None,
    description: Optional[str] = None,
) -> list[dict]:
    """LP token total minted supplies, including those not in circulation.

    Args:
        after_unix_time: Filter outputs, only those with a "timestamp" greater than or
            equal to after_unix_time will be returned. If None, all snapshots ever will
            be returned.
        asset_id: Filter for "asset".
        description: Filter for the "for" field.

    Returns:
        List of dicts, containing total supplies of LP tokens at given times.

        Ordered descending by "timestamp", newest first.

        Dict structure:

        id (int): DB primary key.
        for (str): Human readable description.
        asset (str): policy_id.asset_name, in hex.
        amount (int): LP token's total supply at "timestamp".
        timestamp (int): Unix time of the snapshot, in seconds.
        created_at (str): DB entry creation timestamp.
        updated_at (str): DB entry last update timestamp.

    Example:
        >>> supplies = liquidity_pools_circulating_supply(1680385500)
        >>> supplies[-3]
        {'id': 675,
         'for': 'Wingriders iUSD/ADA LP Token',
         'asset': '026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570.452089abb5bf8cc59b678a2cd7b9ee952346c6c0aa1cf27df324310a70d02fc3',
         'amount': 9223372036854774807,
         'timestamp': 1680385562,
         'created_at': '2023-04-01T21:46:02.000000Z',
         'updated_at': '2023-04-01T21:46:02.000000Z'}
    """
    params: dict[str, float | str] = {}
    if after_unix_time is not None:
        params["after"] = after_unix_time
    if asset_id is not None:
        params["asset"] = asset_id
    if description is not None:
        params["for"] = description
    response = requests.get(
        BASE_URL + "/liquidity-pools/circulating-supply", params=params, timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def liquidity_positions(
    at_unix_time: Optional[float], pkhs: Optional[list[str]] = None
) -> list[dict]:
    """Individual accounts' Indigo-staked LP token balances.

    Args:
        at_unix_time: Show staked LP token balances for a given Unix time.
            "None" to get current balances.
        pkhs: Filter output "owner" fields based on this list.

    Returns:
        List of dicts, where each entry contains an account's Indigo-staked LP token
        balance at the given time.

        Dict structure:

        output_hash (str): Tx hash where the LP tokens were locked.
        output_index (int): Tx index of the script-owned tx output which holds the LP
            tokens.
        owner (str): Special account PaymentKeyHash in hex of the wallet that deposited
            LP tokens in the entry to Indigo, and can withdraw them.
        value (str): JSON string. The embedded data structure is a dict. Its entries:
            lovelace (int): Amount of ADA in lovelaces in the LP token script tx output.
            <lp_token_1> (str): Number of LP tokens held by the account, where the
                <lp_token> key identifies which LP token this entry is for. Key's format
                is the same as "lp_token" and "token" fields of other API responses.
                Which is the LP token's policy ID and name in hex format, concatted
                with a "." char. Note that the value is a string, not an integer.
            <lp_token_n> (str): An account can have multiple different LP tokens staked.

    Examples:
        >>> staked_lp = liquidity_positions(1681989753)  # 2023 April 20 11:22:33 UTC
        >>> len(staked_lp)
        221
        >>> staked_lp[-1]
        {'output_hash': 'c2af814cd906e004f121c99c04e12f05ba737531a122aab84b1a73f5963ba5ec',
         'output_index': 0,
         'owner': '915501500137bbfc512cb66c2e58410958e3480365b87e499ee2e296',
         'value': '{"lovelace": 1680900, '
                  '"026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570.452089abb5bf8cc59b678a2cd7b9ee952346c6c0aa1cf27df324310a70d02fc3": "180081167", '
                  '"026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570.562b9ff903fe8d9e1c980120a233051e7b1518cfc75eb9b4227f7710b670b6e9": "3933533", '
                  '"026a18d04a0c642759bb3d83b12e3344894e5c1c7b2aeb1a2113a570.63a3b8ee322ea31a931fd1902528809dc681bc650af21895533c9e98fa4bef2e": "1031194"}'}
    """
    url = BASE_URL + "/liquidity-positions"

    if at_unix_time is None and pkhs is None:
        response = requests.get(url, timeout=TIMEOUT)
    else:
        params: dict[str, float | list[str]] = {}
        if at_unix_time is not None:
            params["timestamp"] = at_unix_time
        if pkhs is not None:
            params["pkhs"] = pkhs
        response = requests.post(url, json=params, timeout=TIMEOUT)

    response.raise_for_status()
    return response.json()


def rewards_stability_pool(snapshot_unix_time: float) -> list[dict]:
    """Individual stability pool accounts' balances at a given time.

    Args:
        snapshot_unix_time: Unix time (in seconds) we'd like the SP balance snapshot
            for. Can't be any time, in practice only 21:45 UTC times will work.

    Returns:
        List of dicts, each dict is an individual stability pool account's balance and
        status at the given snapshot time.

        If a PaymentKeyHash has SP positions in different iAssets, they'll have a
        separate entry in the list for each one. Normally each PKH has a single account
        per iAsset, but technically a PKH can open multiple accounts on-chain, in which
        case duplicate owner+asset combinations are possible in this list.

        Dict structure:

        asset (str): iAsset name.
        iasset_staked (int): SP account's balance in iAsset "lovelaces" (i.e. *1M).
        opened_at (int): Unix time (in seconds) when the account was opened, i.e. when
            the SP_ACCOUNT token identifying the stability pool account was minted.
        owner (str): PaymentKeyHash of the owner, in hex.

    Examples:
        >>> rewards_stability_pool(1683236700)[1301:1303]  # 2023 May 4th 21:45:00 UTC
        [{'asset': 'iUSD',
          'iasset_staked': 3654982410,
          'opened_at': 1670376638,
          'owner': 'e0ea68c3e09114bb8b746e67a3e44b5e4c0cdce33c07391dc1f61be2'},
         {'asset': 'iUSD',
          'iasset_staked': 4100717049,
          'opened_at': 1681946235,
          'owner': 'beaf7018117b8306d327558a7e0f0ae32264fc37610bd29eb90d3cd8'}]
        >>> rewards_stability_pool(1683236701)  # 2023 May 4th 21:45:01 UTC
        requests.exceptions.HTTPError: 404 Client Error: Not Found for url: […]
    """
    response = requests.get(
        BASE_URL + "/rewards/stability-pool",
        params={"timestamp": snapshot_unix_time},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def rewards_staking(snapshot_unix_time: float) -> list[dict]:
    """Reward-eligible INDY that each governance account has staked at a given time.

    Args:
        snapshot_unix_time: Unix time (in seconds) to get eligible INDY balances for.
            Has to be a Cardano nominal epoch rollover time, i.e. exactly 21:45 UTC
            every five days.

    Returns:
        List of dicts, each dict containing a PKH and its reward-eligible INDY balance.

        Dict structure:

        owner (str): PaymentKeyHash of the owner, in hex.
        staked (int): Reward-eligible INDY amount of the owner, in INDY lovelaces
            (i.e. multiplied by a million)

    Examples:

        A Cardano epoch snapshot time, 2023 January 20 21:45 UTC:

        >>> rewards_staking(1674251100)[:3]
        [{'owner': 'dd4ec1a00770d0659820e0083be64e233a9da64af048ed52e2c9bf00',
          'staked_indy': 50200803},
         {'owner': '3de5bd9affd4d3a8f02cdf5c1fc30889db7338396507f4309c1c48b3',
          'staked_indy': 74000000},
         {'owner': '96fd26a13808a0837bcf27d13c369a17a98c3f22a3203569958f4183',
          'staked_indy': 55200803}]

        Not an epoch snapshot, 2023 January 22 21:45 UTC:

        >>> rewards_staking(1674423900)
        requests.exceptions.HTTPError: 404 Client Error: Not Found for url: […]
    """
    response = requests.get(
        BASE_URL + "/rewards/staking",
        params={"timestamp": snapshot_unix_time},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()
