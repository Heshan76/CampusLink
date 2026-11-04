import unittest

from campuslink.config import ExperimentConfig
from campuslink.contact import find_contacts, manhattan
from campuslink.experiment import run_batch
from campuslink.models import Message, MessageResult, Node
from campuslink.movement import move_node, valid_moves
from campuslink.routing import DirectRouter, EpidemicRouter
from campuslink.scenario import generate_scenario, scenario_from_config
from campuslink.simulator import Simulation, run_simulation, summarize
from tests.helpers import contacts

CFG = ExperimentConfig()


def msg(src, dst, mid=1):
    return Message(mid, src, dst, 0)


class MovementTests(unittest.TestCase):
    def setUp(self):
        self.sc = scenario_from_config(CFG, 40, 1)

    def test_01_nodes_start_inside_grid(self):
        for x, y in self.sc.positions_by_step[0]:
            self.assertTrue(0 <= x < CFG.grid_width and 0 <= y < CFG.grid_height)

    def test_02_nodes_never_leave_grid(self):
        for step in self.sc.positions_by_step:
            for x, y in step:
                self.assertTrue(0 <= x < CFG.grid_width and 0 <= y < CFG.grid_height)

    def test_02b_corner_and_edge_moves_are_legal(self):
        self.assertEqual(len(valid_moves(0, 0, 16, 16)), 2)
        self.assertEqual(len(valid_moves(0, 5, 16, 16)), 3)
        self.assertEqual(len(valid_moves(5, 5, 16, 16)), 4)
        for (dx, dy) in valid_moves(15, 15, 16, 16):
            self.assertTrue(0 <= 15 + dx < 16 and 0 <= 15 + dy < 16)

    def test_03_each_step_is_stay_or_one_cell_horizontally_or_vertically(self):
        t = self.sc.positions_by_step
        self.assertEqual(len(t), CFG.max_steps + 1)
        stays = moves = 0
        for s in range(CFG.max_steps):
            for n in range(40):
                d = manhattan(t[s][n], t[s + 1][n])
                self.assertIn(d, (0, 1))          # never 2 (no diagonal) and never a jump
                stays += d == 0
                moves += d == 1
        self.assertGreater(stays, 0)              # staying really happens (proposal: "stay or move")
        self.assertGreater(moves, 0)

    def test_03a_grid_is_the_proposal_18_by_6(self):
        self.assertEqual((CFG.grid_width, CFG.grid_height), (18, 6))
        xs = {x for step in self.sc.positions_by_step for x, _ in step}
        ys = {y for step in self.sc.positions_by_step for _, y in step}
        self.assertTrue(max(xs) <= 17 and max(ys) <= 5)
        self.assertGreater(max(xs), 5)            # nodes really use the long side

    def test_03b_no_wraparound_from_a_corner(self):
        import random
        node = Node(0, 0, 0)
        rng = random.Random(1)
        for _ in range(500):
            move_node(node, rng, 16, 16)
            self.assertTrue(0 <= node.x < 16 and 0 <= node.y < 16)


class ContactTests(unittest.TestCase):
    def test_04_contact_rule_radius_1(self):
        self.assertEqual(len(find_contacts([(3, 3), (3, 3)], 1, 0)), 1)   # same cell
        self.assertEqual(len(find_contacts([(3, 3), (3, 4)], 1, 0)), 1)   # vertical neighbour
        self.assertEqual(len(find_contacts([(3, 3), (4, 3)], 1, 0)), 1)   # horizontal neighbour
        self.assertEqual(len(find_contacts([(3, 3), (4, 4)], 1, 0)), 0)   # diagonal: NOT a contact
        self.assertEqual(len(find_contacts([(3, 3), (3, 5)], 1, 0)), 0)   # two cells away

    def test_04b_radius_is_configurable(self):
        self.assertEqual(len(find_contacts([(3, 3), (4, 4)], 2, 0)), 1)

    def test_04c_contact_order_is_deterministic(self):
        pos = [(1, 1), (1, 2), (1, 1), (5, 5)]
        c = [(x.node_a, x.node_b) for x in find_contacts(pos, 1, 0)]
        self.assertEqual(c, sorted(c))

    def test_05_non_contacting_nodes_cannot_exchange(self):
        r = EpidemicRouter([msg(0, 2)])
        r.process_step(0, [])                       # nobody is close to anybody
        self.assertEqual(r.states[0].holders, {0})
        r.process_step(1, contacts((1, 2)))         # 1 meets 2, but 1 holds nothing
        self.assertEqual(r.states[0].holders, {0})
        self.assertFalse(r.states[0].delivered)


class DirectTests(unittest.TestCase):
    def test_06_intermediate_node_never_gets_message(self):
        r = DirectRouter([msg(0, 2)])
        r.process_step(0, contacts((0, 1)))
        r.process_step(1, contacts((1, 2)))
        st = r.states[0]
        self.assertNotIn(1, st.holders)
        self.assertFalse(st.delivered)
        self.assertEqual(st.copies_created, 0)

    def test_07_delivers_only_on_destination_encounter(self):
        r = DirectRouter([msg(0, 2)])
        r.process_step(5, contacts((0, 2)))
        st = r.states[0]
        self.assertTrue(st.delivered)
        self.assertEqual(st.delivery_step, 5)
        self.assertEqual(st.copies_created, 0)       # hand-over of the original, not a copy
        self.assertEqual(st.holders, {2})


class EpidemicTests(unittest.TestCase):
    def test_08_copy_created_on_contact(self):
        r = EpidemicRouter([msg(0, 5)])
        r.process_step(0, contacts((0, 1)))
        st = r.states[0]
        self.assertEqual(st.holders, {0, 1})
        self.assertEqual(st.copies_created, 1)

    def test_09_no_duplicate_copies(self):
        r = EpidemicRouter([msg(0, 5)])
        r.process_step(0, contacts((0, 1)))
        r.process_step(1, contacts((0, 1)))                  # already shared: nothing new
        self.assertEqual(r.states[0].copies_created, 1)
        r.process_step(2, contacts((0, 2), (1, 2)))          # two holders touch node 2 in ONE step
        self.assertEqual(r.states[0].copies_created, 2)
        r.process_step(3, contacts((0, 2), (1, 2)))
        self.assertEqual(r.states[0].copies_created, 2)
        self.assertEqual(r.states[0].holders, {0, 1, 2})

    def test_09b_one_hop_per_step(self):
        r = EpidemicRouter([msg(0, 9)])
        r.process_step(0, contacts((0, 1), (1, 2)))          # 2 is two hops away
        self.assertEqual(r.states[0].holders, {0, 1})

    def test_09c_destination_delivery_and_replication_stops(self):
        r = EpidemicRouter([msg(0, 2)])
        r.process_step(0, contacts((0, 1)))
        r.process_step(1, contacts((1, 2), (0, 3)))          # delivery wins, node 3 gets nothing
        st = r.states[0]
        self.assertTrue(st.delivered)
        self.assertEqual(st.delivery_step, 1)
        self.assertEqual(st.holders, {0, 1, 2})
        self.assertEqual(st.copies_created, 2)               # node 1 and destination 2
        r.process_step(2, contacts((0, 4), (2, 5)))          # after delivery: no more copies
        self.assertEqual(st.copies_created, 2)

    def test_09d_contact_order_does_not_change_result(self):
        pairs = [(0, 1), (1, 2), (0, 3), (3, 4), (2, 4)]
        a, b = EpidemicRouter([msg(0, 9)]), EpidemicRouter([msg(0, 9)])
        a.process_step(0, contacts(*pairs))
        b.process_step(0, contacts(*reversed(pairs)))
        self.assertEqual(a.states[0].holders, b.states[0].holders)
        self.assertEqual(a.states[0].copies_created, b.states[0].copies_created)


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.sc = scenario_from_config(CFG, 20, 3)

    def test_10_delivered_messages_have_valid_times(self):
        for method in ("DIRECT", "EPIDEMIC"):
            run = run_simulation(self.sc, method, CFG, "t", 3)
            for m in run.messages:
                if m.delivered:
                    self.assertGreaterEqual(m.delivery_time_steps, 0)
                    self.assertEqual(m.delivery_time_steps, m.delivery_step - m.creation_step)
                    self.assertLessEqual(m.delivery_step, CFG.max_steps)

    def test_11_undelivered_messages_have_no_time(self):
        sc = generate_scenario("short", 7, 10, 16, 16, 3, 6)       # only 3 steps -> undelivered
        run = run_simulation(sc, "DIRECT", CFG, "t", 1)
        undelivered = [m for m in run.messages if not m.delivered]
        self.assertTrue(undelivered)
        for m in undelivered:
            self.assertIsNone(m.delivery_step)
            self.assertIsNone(m.delivery_time_steps)

    def test_11b_summary_math(self):
        mk = lambda d, t: MessageResult(1, 0, 1, 0, d, t, t, 0, 0)
        total, delivered, pct, avg, copies, _ = summarize([mk(True, 10), mk(True, 20), mk(False, None), mk(False, None)])
        self.assertEqual((total, delivered, pct, avg), (4, 2, 50.0, 15.0))   # undelivered NOT counted as 0
        _, _, pct0, avg0, _, _ = summarize([mk(False, None)])
        self.assertEqual(pct0, 0.0)
        self.assertIsNone(avg0)

    def test_12_copy_counts_correct(self):
        d = run_simulation(self.sc, "DIRECT", CFG, "t", 3)
        self.assertEqual(d.total_copies_created, 0)
        sim = Simulation(self.sc, "EPIDEMIC", CFG.contact_radius)
        sim.run_to_end()
        for st in sim.router.states:
            self.assertGreaterEqual(st.copies_created, 0)
            self.assertEqual(st.copies_created, len(st.holders) - 1)   # every extra holder = one copy
        e = run_simulation(self.sc, "EPIDEMIC", CFG, "t", 3)
        self.assertEqual(e.total_copies_created, sum(m.copies_created for m in e.messages))

    def test_12b_epidemic_never_slower_than_direct_on_same_scenario(self):
        for rep in range(1, 6):
            sc = scenario_from_config(CFG, 20, rep)
            d = run_simulation(sc, "DIRECT", CFG, "t", rep)
            e = run_simulation(sc, "EPIDEMIC", CFG, "t", rep)
            for dm, em in zip(d.messages, e.messages):
                if dm.delivered:
                    self.assertTrue(em.delivered)
                    self.assertLessEqual(em.delivery_step, dm.delivery_step)


class ReproducibilityTests(unittest.TestCase):
    def test_13_same_seed_same_scenario_and_result(self):
        a, b = scenario_from_config(CFG, 20, 4), scenario_from_config(CFG, 20, 4)
        self.assertEqual(a.positions_by_step, b.positions_by_step)
        self.assertEqual(a.messages, b.messages)
        ra = run_simulation(a, "EPIDEMIC", CFG, "t", 4)
        rb = run_simulation(b, "EPIDEMIC", CFG, "t", 4)
        self.assertEqual(ra.messages, rb.messages)
        self.assertEqual(ra.total_copies_created, rb.total_copies_created)

    def test_13b_different_seed_different_scenario(self):
        self.assertNotEqual(scenario_from_config(CFG, 20, 1).positions_by_step,
                            scenario_from_config(CFG, 20, 2).positions_by_step)

    def test_13c_messages_have_distinct_source_and_destination(self):
        for rep in range(1, 11):
            for n in (10, 20, 40):
                sc = scenario_from_config(CFG, n, rep)
                self.assertEqual(len(sc.messages), CFG.messages_per_run)
                self.assertEqual(len({m.message_id for m in sc.messages}), CFG.messages_per_run)
                for m in sc.messages:
                    self.assertNotEqual(m.source, m.destination)
                    self.assertTrue(0 <= m.source < n and 0 <= m.destination < n)

    def test_14_paired_runs_use_identical_movement(self):
        runs = run_batch(CFG, "t", [(20, 2, "DIRECT"), (20, 2, "EPIDEMIC")])
        self.assertEqual(runs[0].trace_hash, runs[1].trace_hash)
        self.assertEqual(runs[0].random_seed, runs[1].random_seed)
        self.assertEqual(runs[0].scenario_id, runs[1].scenario_id)

    def test_14b_running_a_method_does_not_change_the_scenario(self):
        sc = scenario_from_config(CFG, 20, 2)
        before = sc.trace_hash()
        run_simulation(sc, "EPIDEMIC", CFG, "t", 2)
        run_simulation(sc, "DIRECT", CFG, "t", 2)
        self.assertEqual(sc.trace_hash(), before)
        self.assertEqual(before, scenario_from_config(CFG, 20, 2).trace_hash())

    def test_14d_run_continues_through_all_steps_by_default(self):
        sc = scenario_from_config(CFG, 40, 1)
        run = run_simulation(sc, "EPIDEMIC", CFG, "t", 1)
        self.assertEqual(run.steps_simulated, CFG.max_steps)     # proposal: continue through 180 steps

    def test_14e_runs_in_one_batch_share_the_session_timestamp(self):
        runs = run_batch(CFG, "t", [(10, 1, "DIRECT"), (10, 1, "EPIDEMIC"), (20, 2, "DIRECT")])
        self.assertEqual(len({r.run_timestamp for r in runs}), 1)

    def test_14c_pilot_and_official_seeds_never_overlap(self):
        official = {CFG.seed_for(n, r) for n in CFG.node_counts for r in range(1, 11)}
        pilot = {CFG.seed_for(n, r, pilot=True) for n in CFG.node_counts for r in range(1, 11)}
        self.assertEqual(len(official), 30)
        self.assertFalse(official & pilot)


if __name__ == "__main__":
    unittest.main()
