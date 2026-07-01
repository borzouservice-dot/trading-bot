def position_risk(balance, base_risk, weight):
    return balance * base_risk * weight


def apply_trade(balance, risk_amount, rr):

    pnl = risk_amount * rr

    balance += pnl

    return balance, pnl


def drawdown(max_balance, balance):

    if max_balance <= 0:
        return 0

    return round(
        (max_balance - balance)
        / max_balance * 100,
        2
    )


def winrate(wins, trades):

    if trades == 0:
        return 0

    return round(
        wins / trades * 100,
        2
    )
