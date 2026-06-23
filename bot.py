import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import time

# ================= CONFIG =================
STATE_SIZE = 5
ACTIONS = ["LONG", "SHORT", "HOLD"]

GAMMA = 0.95
LR = 0.001
BATCH_SIZE = 32
MEMORY = []

# ================= MODEL =================
class DQN(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(STATE_SIZE, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, 3)
        )

    def forward(self, x):
        return self.net(x)


policy = DQN()
target = DQN()
target.load_state_dict(policy.state_dict())

opt = optim.Adam(policy.parameters(), lr=LR)
loss_fn = nn.MSELoss()

# ================= STATE =================
def get_state(prices):
    prices = np.array(prices)

    if len(prices) < 20:
        return np.zeros(STATE_SIZE)

    return np.array([
        prices[-1] - prices[-2],
        np.mean(prices[-5:]),
        np.mean(prices[-20:]),
        np.std(prices[-10:]),
        prices[-1] - np.min(prices[-20:])
    ], dtype=np.float32)


# ================= MEMORY =================
def store(exp):
    if len(MEMORY) > 5000:
        MEMORY.pop(0)
    MEMORY.append(exp)


# ================= ACT =================
def act(state, eps=0.1):
    if random.random() < eps:
        return random.randint(0, 2)

    state = torch.tensor(state, dtype=torch.float32).unsqueeze(0)
    return torch.argmax(policy(state)).item()


# ================= REWARD =================
def reward(entry, exit_price, side):
    if side == "LONG":
        return exit_price - entry
    if side == "SHORT":
        return entry - exit_price
    return 0


# ================= TRAIN =================
def train():

    if len(MEMORY) < BATCH_SIZE:
        return

    batch = random.sample(MEMORY, BATCH_SIZE)

    states, actions, rewards, next_states = zip(*batch)

    states = torch.tensor(np.array(states), dtype=torch.float32)
    next_states = torch.tensor(np.array(next_states), dtype=torch.float32)
    actions = torch.tensor(actions)
    rewards = torch.tensor(rewards, dtype=torch.float32)

    q_values = policy(states).gather(1, actions.unsqueeze(1)).squeeze()

    with torch.no_grad():
        next_q = target(next_states).max(1)[0]

    targets = rewards + GAMMA * next_q

    loss = loss_fn(q_values, targets)

    opt.zero_grad()
    loss.backward()
    opt.step()


# ================= MARKET =================
def fake_price(p):
    return p + random.randint(-2, 2)


# ================= LOOP =================
def run():

    prices = [100]
    position = None
    entry = 0
    entry_action = 2

    print("🚀 FIXED RL SYSTEM RUNNING")

    while True:

        price = fake_price(prices[-1])
        prices.append(price)

        state = get_state(prices)
        action = act(state)

        # OPEN
        if position is None and action != 2:
            position = True
            entry = price
            entry_action = action
            print("OPEN", ACTIONS[action], price)

        # CLOSE
        elif position:
            r = reward(entry, price, ACTIONS[entry_action])
            next_state = get_state(prices)

            store((state, entry_action, r, next_state))

            train()

            print("CLOSE PnL:", round(r, 2))

            position = None

        time.sleep(0.5)


if __name__ == "__main__":
    run()
