import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

# =========================
# CONFIG
# =========================
STATE_SIZE = 5
ACTIONS = ["LONG", "SHORT", "HOLD"]

GAMMA = 0.95
LR = 0.001
MEMORY_SIZE = 5000
BATCH_SIZE = 32

# =========================
# FEATURE ENGINE
# =========================
def get_state(closes):
    closes = np.array(closes)

    if len(closes) < 20:
        return np.zeros(STATE_SIZE)

    return np.array([
        (closes[-1] - closes[-2]) / closes[-2],
        np.mean(closes[-5:]) / closes[-1],
        np.mean(closes[-20:]) / closes[-1],
        np.std(closes[-10:]) / closes[-1],
        closes[-1] - np.min(closes[-20:])
    ], dtype=np.float32)


# =========================
# DQN MODEL
# =========================
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


# =========================
# AGENT
# =========================
class Agent:
    def __init__(self):

        self.model = DQN()
        self.target = DQN()
        self.target.load_state_dict(self.model.state_dict())

        self.memory = []
        self.optimizer = optim.Adam(self.model.parameters(), lr=LR)

    def act(self, state, epsilon=0.1):

        if random.random() < epsilon:
            return random.randint(0, 2)

        state = torch.tensor(state, dtype=torch.float32)
        q_values = self.model(state)

        return torch.argmax(q_values).item()

    def store(self, exp):

        if len(self.memory) > MEMORY_SIZE:
            self.memory.pop(0)

        self.memory.append(exp)


# =========================
# REWARD FUNCTION
# =========================
def reward(entry, exit_price, side):

    if side == "LONG":
        return exit_price - entry

    if side == "SHORT":
        return entry - exit_price

    return 0


# =========================
# TRAINING
# =========================
def train(agent):

    if len(agent.memory) < BATCH_SIZE:
        return

    batch = random.sample(agent.memory, BATCH_SIZE)

    for state, action, r, next_state, done in batch:

        state = torch.tensor(state, dtype=torch.float32)
        next_state = torch.tensor(next_state, dtype=torch.float32)

        q_val = agent.model(state)[action]

        target = r

        if not done:
            target += GAMMA * torch.max(agent.target(next_state))

        loss = (q_val - target) ** 2

        agent.optimizer.zero_grad()
        loss.backward()
        agent.optimizer.step()


# =========================
# SIMULATED MARKET
# =========================
def fake_market():

    price = 100 + random.randint(-5, 5)
    return price


# =========================
# MAIN LOOP
# =========================
def run():

    agent = Agent()

    closes = []
    position = None

    entry_price = 0
    entry_action = None

    print("🚀 LEVEL 8 RL TRADING SYSTEM STARTED")

    while True:

        price = fake_market()
        closes.append(price)

        if len(closes) > 100:
            closes.pop(0)

        state = get_state(closes)
        action = agent.act(state)

        # OPEN POSITION
        if position is None and action != 2:

            position = True
            entry_price = price
            entry_action = action

            print(f"OPEN {ACTIONS[action]} @ {price}")

        # CLOSE POSITION
        elif position:

            r = reward(entry_price, price, ACTIONS[entry_action])

            next_state = get_state(closes)

            agent.store((state, entry_action, r, next_state, True))

            train(agent)

            print(f"CLOSE | PnL: {r:.2f}")

            position = None

        # slow loop
        import time
        time.sleep(1)


# =========================
# START
# =========================
if __name__ == "__main__":
    run()
