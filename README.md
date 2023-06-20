# Indy Rewards

[![Python: 3.10, 3.11](https://img.shields.io/badge/python-3.10_|_3.11-2ea44f?logo=python)](https://python.org)
[![Code style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Tool for calculating INDY rewards.

## Installation

```shell
python3 -m venv venv

# Unix-like
source venv/bin/activate

# Windows
.\venv\Scripts\activate

pip install .
```

## Examples

<details>
<summary>Summary (epoch)</summary>

```console
$ indy-rewards summary 415
                                          Purpose       Amount
                              INDY staking reward  2397.999981
   Reward for providing iBTC liquidity on Minswap   446.794352
Reward for providing iBTC liquidity on WingRiders  1296.403523
   Reward for providing iETH liquidity on Minswap    44.112269
Reward for providing iETH liquidity on WingRiders  1518.083264
   Reward for providing iUSD liquidity on Minswap   773.708751
Reward for providing iUSD liquidity on WingRiders   715.897850
                               SP reward for iBTC  7587.745284
                               SP reward for iETH  7510.028148
                               SP reward for iUSD 13670.226556
                        Total INDY staking reward  2397.999981
                                  Total LP reward  4795.000009
                                  Total SP reward 28767.999988
                                            Total 35960.999978
```

</details>

<details>
<summary>Summary (daily)</summary>

```console
$ indy-rewards summary 2023-05-29
                                          Purpose      Amount
   Reward for providing iBTC liquidity on Minswap   87.805790
Reward for providing iBTC liquidity on MuesliSwap    0.314330
Reward for providing iBTC liquidity on WingRiders  246.196969
   Reward for providing iETH liquidity on Minswap    8.319801
Reward for providing iETH liquidity on WingRiders  314.210358
   Reward for providing iUSD liquidity on Minswap  155.789009
Reward for providing iUSD liquidity on MuesliSwap    2.432399
Reward for providing iUSD liquidity on WingRiders  143.931346
                               SP reward for iBTC 1479.633104
                               SP reward for iETH 1507.802750
                               SP reward for iUSD 2766.164154
                                  Total LP reward  959.000002
                                  Total SP reward 5753.600008
                                            Total 6712.600010
```

</details>

<details>
<summary>PKH filter</summary>

For example, filtering for these two wallets (PKHs):

-   `aada39748edc9f40ec53f879499a837f6badf180413fc03a7a345609`
-   `6699280ab41b732e26e7d3cb02d57f61a76bc8e9a0ceccca4997b812`

```console
$ indy-rewards summary --pkh aada --pkh 6699 416
                                          Purpose   Amount
                              INDY staking reward 0.115320
Reward for providing iUSD liquidity on WingRiders 0.021053
                        Total INDY staking reward 0.115320
                                  Total LP reward 0.021053
                                            Total 0.136373
```

The PKH (payment key hash) is the wallet address thing shown in the upper right
corner of the website, with a wallet connected.

You can filter for one or more PKHs with most commands. You don't have to
input the entire PKH, the first few characters generally identify a PKH.

Works with daily and CSV outputs too:

```console
$ indy-rewards sp --pkh d7346fcd 2023-06-13
 Period                                                  Address            Purpose       Date   Amount       Expiration      AvailableAt
    418 d7346fcd395de69e62f4a2bafbc32af393ceecb3287b0ff4442ff36e SP reward for iETH 2023-06-13 0.707993 2023-09-12 21:45 2023-06-14 23:00
    418 d7346fcd395de69e62f4a2bafbc32af393ceecb3287b0ff4442ff36e SP reward for iBTC 2023-06-13 0.000016 2023-09-12 21:45 2023-06-14 23:00
    418 d7346fcd395de69e62f4a2bafbc32af393ceecb3287b0ff4442ff36e SP reward for iUSD 2023-06-13 0.006158 2023-09-12 21:45 2023-06-14 23:00
```

Filtered file output:

```console
$ indy-rewards sp --pkh d7346f --outfile output.csv 2023-06-13
```

Error if a partial PKH isn't unique:

```console
$ indy-rewards sp --pkh d7 2023-06-13
Usage: indy-rewards sp [OPTIONS] EPOCH_OR_DATE
Try 'indy-rewards sp --help' for help.

Error: Invalid value: PKH start 'd7' matches 6 PKHs. Please use a longer string.
```

Technically the PKH is one of potentially many PKHs of the wallet. The Indigo
web app uses only the first (`/0`) PKH to identify a wallet and to interact
with smart contracts, which is the
[payment part](https://cips.cardano.org/cips/cip19/#paymentpart)
of the wallet's first address.

</details>

<details>
<summary>All rewards for all wallets</summary>

Entire epoch. Daily SP, LP, governance rewards for 5 days:

```console
$ indy-rewards all 414
Period,Address,Purpose,Date,Amount,Expiration,AvailableAt
 Period                                                  Address              Purpose       Date     Amount       Expiration      AvailableAt
    415 198836d653f267dfed06bd383b80539c50f3ab6d6e7e0de11d9b723e   SP reward for iETH 2023-05-26   0.001281 2023-08-28 21:45 2023-05-30 23:00
    415 43b8e3375ecf90169230d91ce92863d0b041ed4c8668cc87d17ea980   SP reward for iETH 2023-05-26   0.006236 2023-08-28 21:45 2023-05-30 23:00
    415 b95d828645f43c1711afad5a374ea6879f95832f50bf249e5e2a8820   SP reward for iETH 2023-05-26   0.372688 2023-08-28 21:45 2023-05-30 23:00
    …
```

Single day:

```console
$ indy-rewards all 2023-05-28
 Period                                                  Address             Purpose       Date     Amount       Expiration      AvailableAt
    415 198836d653f267dfed06bd383b80539c50f3ab6d6e7e0de11d9b723e   SP reward for iETH 2023-05-28   0.001253 2023-08-28 21:45 2023-05-30 23:00
    415 43b8e3375ecf90169230d91ce92863d0b041ed4c8668cc87d17ea980   SP reward for iETH 2023-05-28   0.006102 2023-08-28 21:45 2023-05-30 23:00
    415 b95d828645f43c1711afad5a374ea6879f95832f50bf249e5e2a8820   SP reward for iETH 2023-05-28   0.364700 2023-08-28 21:45 2023-05-30 23:00
    …
```

File output:

```console
$ indy-rewards all 414 -o 414.csv
```

</details>

<details>
<summary>SP rewards only</summary>

```console
$ indy-rewards sp 415
 Period                                                  Address            Purpose       Date     Amount       Expiration      AvailableAt
    416 198836d653f267dfed06bd383b80539c50f3ab6d6e7e0de11d9b723e SP reward for iETH 2023-05-31   0.001206 2023-09-02 21:45 2023-06-04 23:00
    416 43b8e3375ecf90169230d91ce92863d0b041ed4c8668cc87d17ea980 SP reward for iETH 2023-05-31   0.005873 2023-09-02 21:45 2023-06-04 23:00
    416 b95d828645f43c1711afad5a374ea6879f95832f50bf249e5e2a8820 SP reward for iETH 2023-05-31   0.350988 2023-09-02 21:45 2023-06-04 23:00
    …
```

</details>

<details>
<summary>LP rewards only</summary>

```console
$ indy-rewards lp 415
 Period                                                  Address                                           Purpose       Date     Amount       Expiration      AvailableAt
    416 b8a892490fa5784bf2c73603b7cc0f05a3219fc7901db3e698ad7f11 Reward for providing iBTC liquidity on WingRiders 2023-05-31   0.021726 2023-09-02 21:45 2023-06-04 23:00
    416 d522cfaab057a5a8aed4e83723ae0fa5150f007e009aab2e77659701 Reward for providing iBTC liquidity on WingRiders 2023-05-31   0.022166 2023-09-02 21:45 2023-06-04 23:00
    416 060fde906d7f945bd899dc8831910340f5afe83da6f576fa9d0040a1 Reward for providing iBTC liquidity on WingRiders 2023-05-31   0.049467 2023-09-02 21:45 2023-06-04 23:00
    …
```

</details>

<details>
<summary>INDY governance staking rewards only</summary>

```console
$ indy-rewards gov 415
 Period                                                  Address             Purpose       Date     Amount       Expiration      AvailableAt
    416 06efd1d2dfa9f2121644765e0bf1d3c2ccc3db6084ef3724de2e901c INDY staking reward 2023-06-04   0.046039 2023-09-02 21:45 2023-06-04 23:00
    416 5706ea516b1a0f350b6876b84e02317af4c8b886c74562d9d9cb1764 INDY staking reward 2023-06-04   0.038790 2023-09-02 21:45 2023-06-04 23:00
    416 13a1d9bb7849716bd993b520f975175ae1b6720fec18dab37435d095 INDY staking reward 2023-06-04   0.095708 2023-09-02 21:45 2023-06-04 23:00
    …
```

</details>

<details>
<summary>LP token staking INDY APR</summary>

Historical APRs, extrapolated either for a day or an epoch, based on:
https://docs.indigoprotocol.io/resources/protocol-statistics/apr-apy-calculations.

Keep in mind that APRs can't be predicted, they rely on future events and can
change significantly depending on users' actions.

Single day:

```console
$ indy-rewards lp-apr 2023-06-07

iBTC
Minswap: 62.87%
WingRiders: 51.28%

iETH
Minswap: 19.20%
WingRiders: 29.90%

iUSD
Minswap: 5.91%
WingRiders: 5.45%
```

Epoch 5-day average:

```console
$ indy-rewards lp-apr 416

iBTC
Minswap: 62.60%
WingRiders: 50.77%

iETH
Minswap: 27.06%
WingRiders: 57.56%

iUSD
Minswap: 13.03%
WingRiders: 12.02%
```

</details>

<details>
<summary>SP staking INDY APR</summary>

Single day:

```console
$ indy-rewards sp-apr 2023-06-01
iBTC: 38.20%
iETH: 39.09%
iUSD: 49.12%
```

Epoch 5-day average:

```console
$ indy-rewards sp-apr 417
iBTC: 66.96%
iETH: 73.64%
iUSD: 84.42%
```

</details>

## Development

```shell
pip install --editable .
pip install -r requirements-dev.txt
pre-commit install

# Pre-commit checks will automatically run for staged files on git commit.
# This is how to manually run them for all files.
pre-commit run --all-files

# Run tests.
pytest
```
