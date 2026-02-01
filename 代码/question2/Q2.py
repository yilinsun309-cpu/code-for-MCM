import heapq, random, math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

INF = 10**30

def exp_time(rate: float) -> float:
    """Sample exponential waiting time with rate > 0."""
    if rate <= 0:
        return INF
    u = random.random()
    return -math.log(1 - u) / rate

@dataclass
class Rocket:
    rid: int
    state: int          # 2,3,4,5 or 6
    payload: float      # q_r
    alive: bool = True

@dataclass(order=True)
class Event:
    time: float
    etype: str = field(compare=False)     # "rocket", "elevator", "replace"
    rid: Optional[int] = field(default=None, compare=False)
    count: int = field(default=0, compare=False)  # for replace arrivals

class Simulator:
    def __init__(self,
                 scenario_h: int,
                 tau: Dict[int, float],             # duration per program (days)
                 p_fail: Dict[int, float],          # p_{l6} for l in {2,3,4,5}
                 phi: Dict[int, Dict[int, int]],    # phi[h][l]=l'
                 v_e: float,                        # elevator supply rate (ton/day)
                 lambda_down: float,                # Up->Down rate (1/day)
                 lambda_up: float,                  # Down->Up rate (1/day)
                 I_safe: int,
                 delta: float,                      # replacement latency (days)
                 M_goal: float,
                 seed: int = 0):
        random.seed(seed)
        self.h = scenario_h
        self.tau = tau
        self.p_fail = p_fail
        self.phi = phi
        self.v_e = v_e
        self.lambda_down = lambda_down
        self.lambda_up = lambda_up
        self.I_safe = I_safe
        self.delta = delta
        self.M_goal = M_goal

        self.t = 0.0
        self.E = 1  # elevator up/down
        self.S = 0.0  # apex inventory (ton)
        self.M = 0.0  # delivered mass to Moon (ton)
        self.fail_count = 0
        self.rocks: Dict[int, Rocket] = {}
        self.waiting: List[int] = []  # rocket ids waiting for payload

        self.pq: List[Event] = []

    def active_count(self) -> int:
        return sum(1 for r in self.rocks.values() if r.alive and r.state != 6)

    def schedule(self, ev: Event):
        heapq.heappush(self.pq, ev)

    def init_elevator(self):
        # start in Up, schedule first switch
        dt = exp_time(self.lambda_down)
        self.schedule(Event(self.t + dt, "elevator"))

    def add_rocket(self, rid: int, init_state: int, payload: float):
        self.rocks[rid] = Rocket(rid=rid, state=init_state, payload=payload, alive=True)
        # schedule its first completion
        self.schedule(Event(self.t + self.tau[init_state], "rocket", rid=rid))

    def fluid_update(self, new_t: float):
        dt = new_t - self.t
        if dt < 0:
            return
        if self.E == 1:
            self.S += self.v_e * dt
        self.t = new_t

    def try_release_waiting(self):
        # FIFO: try start program 3 for waiting rockets if inventory sufficient
        new_wait = []
        for rid in self.waiting:
            r = self.rocks.get(rid)
            if r is None or r.state == 6:
                continue
            if self.S >= r.payload:
                self.S -= r.payload
                # start program 3 now, schedule completion
                self.schedule(Event(self.t + self.tau[3], "rocket", rid=rid))
                r.state = 3
            else:
                new_wait.append(rid)
        self.waiting = new_wait

    def trigger_replacement(self):
        deficit = max(0, self.I_safe - self.active_count())
        if deficit > 0:
            self.schedule(Event(self.t + self.delta, "replace", count=deficit))

    def handle_elevator(self):
        # switch state
        self.E = 1 - self.E
        # schedule next switch
        rate = self.lambda_down if self.E == 1 else self.lambda_up
        self.schedule(Event(self.t + exp_time(rate), "elevator"))
        # if elevator just became up, inventory will start growing; we can also attempt release now
        self.try_release_waiting()

    def handle_replace(self, count: int):
        # add 'count' rockets; init state depends on scenario
        start_state = 2 if self.h in (2, 3) else 4  # example; adjust if your scenario1 differs
        base_id = max(self.rocks.keys(), default=0) + 1
        for k in range(count):
            self.add_rocket(base_id + k, start_state, payload=125.0)

    def handle_rocket(self, rid: int):
        r = self.rocks.get(rid)
        if r is None or r.state == 6:
            return
        l = r.state

        # completion of program l: if it was delivery, count mass
        if l == 3:
            self.M += r.payload

        # sample failure for l in {2,3,4,5}
        pf = self.p_fail.get(l, 0.0)
        if random.random() < pf:
            # absorbing failure
            r.state = 6
            self.fail_count += 1
            # replacement policy
            self.trigger_replacement()
            return

        # transition to next program
        l_next = self.phi[self.h].get(l, None)
        if l_next is None:
            return
        r.state = l_next

        # if next program requires payload (program 3), need inventory
        if l_next == 3:
            if self.S >= r.payload:
                self.S -= r.payload
                self.schedule(Event(self.t + self.tau[3], "rocket", rid=rid))
            else:
                # wait until enough inventory accumulates; will be retried on elevator events
                self.waiting.append(rid)
        else:
            self.schedule(Event(self.t + self.tau[l_next], "rocket", rid=rid))

    def run(self, max_time_days: float = 1e9):
        while self.pq and self.M < self.M_goal:
            ev = heapq.heappop(self.pq)
            if ev.time > max_time_days:
                break
            self.fluid_update(ev.time)
            if ev.etype == "elevator":
                self.handle_elevator()
            elif ev.etype == "replace":
                self.handle_replace(ev.count)
            elif ev.etype == "rocket":
                self.handle_rocket(ev.rid)

        return {
            "T_star_days": self.t,
            "delivered_M": self.M,
            "failures": self.fail_count,
            "active_rockets": self.active_count(),
            "apex_inventory": self.S,
            "waiting": len(self.waiting),
        }

# ---------- Example config ----------
tau = {2: 0.5, 3: 3.0, 4: 3.0, 5: 4.0}  # days
p_fail = {2: 1.78e-2, 3: 1e-3, 4: 1.03e-2, 5: 0.0}  # p56 TBD -> 0 for now
phi = {
    2: {2: 3, 3: 5, 5: 2},   # scenario 2
    3: {2: 3, 3: 4, 4: 3},   # scenario 3
    1: {3: 4, 4: 3},         # scenario 1 (rocket cycling at apex) example
}

sim = Simulator(
    scenario_h=3,
    tau=tau,
    p_fail=p_fail,
    phi=phi,
    v_e=537000/365,          # ton/day (example)
    lambda_down=0.01,        # 1/day (symbolic)
    lambda_up=1/2.0,         # mean repair 2 days -> rate 0.5/day
    I_safe=70,
    delta=2.0,               # 2 days latency (symbolic)
    M_goal=1e8,              # ton (example)
    seed=1
)

# Initialize
sim.init_elevator()
for i in range(70):
    sim.add_rocket(rid=i+1, init_state=2, payload=125.0)

print(sim.run())