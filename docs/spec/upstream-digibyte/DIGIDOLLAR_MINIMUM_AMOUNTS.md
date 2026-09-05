# DigiDollar Minimum And Maximum Amounts

DigiDollar has a few amount limits. They are easy to mix up, so here is the simple version.

There are two different things:

1. **Minting DigiDollars**: creating new DD by locking DGB collateral.
2. **Sending DigiDollars**: transferring DD that already exists.

They do not use the same minimum.

## Simple Numbers

| Action | Minimum | Maximum |
|---|---:|---:|
| Mint new DD | **$100.00 DD** | **$100,000.00 DD** per mint |
| Send/transfer DD | **$1.00 DD** | **$100,000.00 DD** per output |
| DigiDollar tx fee | **0.1 DGB** | fee policy, not a DD amount |

DigiDollar tracks amounts in cents:

```text
1 cent      = $0.01 DD
100 cents   = $1.00 DD
10000 cents = $100.00 DD
```

## Sending DD

The smallest normal DD payment is **$1.00 DD**.

The largest normal DD transfer output is **$100,000.00 DD**.

So this is valid:

```text
senddigidollar <address> 100
```

That sends **100 cents**, which is **$1.00 DD**.

This is also valid:

```text
senddigidollar <address> 1.00
```

That also sends **$1.00 DD**.

But this is too small:

```text
senddigidollar <address> 0.01
```

That means **$0.01 DD**, and normal DD transfer outputs must be at least **$1.00 DD**.

Also be careful with this:

```text
senddigidollar <address> 1
```

Integer amounts are treated as **cents**, so `1` means **$0.01 DD**, not `$1.00 DD`.

Use `100` or `1.00` to send one DigiDollar.

## Minting DD

Minting has a higher minimum because minting creates new DigiDollars and locks collateral.

On mainnet, mainnet-PRE, and testnet:

```text
Minimum mint: $100.00 DD
Maximum mint: $100,000.00 DD
```

So you cannot mint `$1 DD` or `$10 DD` on mainnet. The minimum mint is **$100 DD**.

You also cannot mint more than **$100,000 DD** in one mint transaction.

After someone has minted DD, they can send it in smaller pieces, but each normal DD output must still be at least **$1 DD**.

## Is A Transfer Transaction Maxed At $100,000 DD?

For a normal one-recipient send, yes:

```text
senddigidollar <address> 10000000
```

That sends **$100,000.00 DD**, because `10000000` means 10,000,000 cents.

But the exact consensus rule is more specific:

```text
Each DD transfer output must be between $1.00 DD and $100,000.00 DD.
```

So the **per-output** maximum is `$100,000 DD`.

A multi-recipient transaction can contain more than one DD output, but each output still has to obey the `$1` minimum and `$100,000` maximum, and the whole transaction must still conserve DD exactly. In other words, a transfer cannot create extra DD. Total DD input must equal total DD output.

Wallet/RPC code also limits each recipient output to `$100,000 DD` and may reject overly large multi-recipient transactions because of normal transaction size and standard relay limits.

## Is This Consensus Enforced?

Yes.

These are not just Qt wallet display rules.

The network enforces the limits:

- A mint below the mint minimum is invalid.
- A mint above the mint maximum is invalid.
- A transfer output below `$1 DD` is invalid.
- A transfer output above `$100,000 DD` is invalid.
- A transfer where total DD input does not equal total DD output is invalid.

The wallet and RPC also check these rules early so users get a clear error before the transaction is broadcast. But even if someone hand-builds a bad transaction, upgraded nodes should reject it.

## What About The 0.1 DGB Fee?

The **0.1 DGB fee** is a miner fee paid in DGB.

It is not the DigiDollar amount.

That means:

```text
Minimum DD transfer: $1.00 DD
Minimum DD mint:     $100.00 DD
Minimum DD tx fee:   0.1 DGB
```

The fee does not let someone send `$0.01 DD`. A `$0.01 DD` transfer output is still too small.

## DD Change

DD change follows the same rule as any other DD transfer output.

If a send creates change, the change must be either:

- exactly `0`, meaning no change; or
- at least **$1.00 DD**.

The wallet tries to avoid creating bad sub-$1 DD change, because the network would reject that transaction.

## Main Takeaway

You can think of it like this:

**Minting starts at $100 DD and maxes out at $100,000 DD per mint. Sending starts at $1 DD and maxes out at $100,000 DD per output. DigiDollar transactions pay at least 0.1 DGB in miner fees.**

Those limits are built into consensus, not just the user interface.
