import gamelib
import random
import math
import warnings
from sys import maxsize
import json
from gamelib.unit import GameUnit
import copy
from collections import deque, namedtuple
from simulator import Simulator
from queue import PriorityQueue
import time

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 
David
Olly
  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""


building = namedtuple('Building', ['name', 'x', 'y'])
attacker = namedtuple('Attacker', ['name', 'x', 'y', 'num'])

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []
        self.p_queue = PriorityQueue()
        self.defence_priority_map = dict()

        self.critical_turrets_non_hammer = []
        self.crtical_walls_non_hammer = []
        self.critical_turrets_hammer = []
        self.critical_walls_hammer = []
        self.critical_supports_non_hammer = []
        self.critical_supports_hammer = []

        self.throw_interceptors = True
        self.thunder_striking = False

        self.can_place = {(13, 0): False, (14, 0): False, (13, 1): False, (14, 1): False, (15, 1): False, (11, 2): False, (12, 2): False, (15, 2): False, (16, 2): False, (10, 3): False, (11, 3): False, (16, 3): False, (17, 3): False, (9, 4): False, (10, 4): False, (17, 4): False, (18, 4): False, (8, 5): False, (9, 5): False, (18, 5): False, (19, 5): False, (7, 6): False, (8, 6): False, (19, 6): False, (20, 6): False, (6, 7): False, (7, 7): False, (20, 7): False, (21, 7): False, (5, 8): False, (6, 8): False, (21, 8): False, (22, 8): False, (4, 9): False, (5, 9): False, (22, 9): False, (23, 9): False, (3, 10): False, (4, 10): False, (5, 10): False, (6, 10): False, (7, 10): False, (8, 10): False, (21, 10): False, (22, 10): False, (23, 10): False, (24, 10): False, (2, 11): False, (3, 11): False, (8, 11): False, (8, 12): False, (8, 13): False, (20, 11): False, (21, 11): False, (24, 11): False, (25, 11): False, (20, 12): False, (20, 13): False}

        # This tracks which wall we are currently blocking off
        self.blocking_wall_placement = "CENTER"

        self.verbose = False

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.

        # Cal total time.
        start_time = time.time()

        self.base_strategy(game_state)
        self.print_map(game_state)

        gamelib.debug_write("Overall time taken for this turn: {}".format(time.time() - start_time))

        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def base_strategy(self, game_state):

        if game_state.turn_number == 0:
            self.inital_add_to_p_queue(game_state)

        # Swap the sides of the blocking wall, if we have already built it.
        self.place_and_remove_blocking_wall(game_state)

        starting = time.time()
        # Firstly repair any damage.
        self.queue_repair_of_critical(game_state)  
        
        time_queuing = time.time()
        # Then build any queued defences.
        self.build_queued_defences(game_state)

        time_building_defence = time.time()
        # If the p_queue is empty then place extra turrets and walls.
        if (self.p_queue.empty() and game_state.get_resource(MP, player_index=0) > 2):
            self.continue_placing_walls_and_turrets(game_state)

        time_placing_extra_walls = time.time()
        if self.throw_interceptors:
            copied_game_state = copy.deepcopy(game_state)
            interceptor_placement = self.find_oppo_best_strategy_and_interceptor_response(copied_game_state)
            if interceptor_placement is not None:
                self.place_attackers(game_state, interceptor_placement)

        time_interceptor = time.time()
        # We now want to search to see if we have a good attack in the one step case.
        # If there is execute this, otherwise do not and carry on.
        self.investigate_and_place_our_immediate_attacks(game_state)
        time_our_attacks = time.time()

        gamelib.debug_write("Time taken per stage: Queueing Repairs: {}   Building Defences: {}   Placing Extra Walls: {}  Placing interceptors: {}  Our attacks: {}".format(time_queuing - starting, time_building_defence - time_queuing, time_placing_extra_walls - time_building_defence, time_interceptor - time_placing_extra_walls, time_our_attacks - time_interceptor))


        # Look ahead to thunder striking in the subsequent turn by rolling out play, and then seeing whether we could  - do enough damange.
        # THUNDER STRIKE PREP



    
    def investigate_and_place_our_immediate_attacks(self, game_state):
        '''
        This should call to get a list of our attacks, and then simulate them to see which is most effective
        args: game_state: GameState
        return: -. Will execute any instructions within this code.
        '''
        my_mp = game_state.get_resource(resource_type=MP, player_index=0)
        if(my_mp >= 6):
            # Get us some attack sets
            attack_sets = self.prepare_immediate_attack_sets_for_us(game_state, my_mp)

            # Look at each in turn to see which is the best.
            best_attack = self.roll_out_our_attack_sets(game_state, attack_sets)

            # This function either Returns
            # None - no good attack which is worth persueing, so we can therefore carry on.
            # List[Attack] at which point we can then use to place these.
            if best_attack is not None:
                self.place_attackers(game_state, best_attack)





    def prepare_immediate_attack_sets_for_us(self, game_state, my_mp):
        ''' return List[Attacker] '''

        # DAVID / HENRY
        

        # Should have Pog scouts left, Pog scouts right, and then stack of Dems.

        attack_set_list = [] #[[attacker(name=SCOUT, x=13, y=0, num=int(my_mp))], [attacker(name=SCOUT, x=14, y=0, num=int(my_mp))], [attacker(name=SCOUT, x=12, y=1, num=min(5, int(my_mp))), attacker(name=SCOUT, x=15, y=1, num=max(0, int(my_mp - 5)))], [attacker(name=SCOUT, x=15, y=1, num=min(5, int(my_mp))), attacker(name=SCOUT, x=12, y=1, num=max(0, int(my_mp - 5)))], [attacker(name=DEMOLISHER, x=13, y=0, num=int(my_mp / 3))]]

        #Attack Profile 1: Big Demo Energy
        demoPos = self.estimate_our_demo_placement(game_state)
        if self.verbose: gamelib.debug_write("Demolisher attack "+ str(demoPos))
        if demoPos is not None:
            attack_set_list.append([attacker(name=DEMOLISHER,x=demoPos[0],y=demoPos[1],num=int(my_mp/3))])
        
        #Attack Profile 2: Scout Rush
        scoutPos = demoPos
        if scoutPos is not None:
            attack_set_list.append([attacker(name=SCOUT,x=scoutPos[0],y=scoutPos[1],num=int(my_mp))])
        #Attack Profile 3: Scout+Demo tomfoolery
        scoutDemoPos = self.get_our_scout_demo_split(game_state)
        if scoutDemoPos is not None and my_mp >= 4:
            scoutPos = scoutDemoPos[0]
            demoPos = scoutDemoPos[1]
            attackSplit = self.get_enemy_scout_demo_split_numbers(my_mp)
            demoNum = attackSplit[0]
            scoutNum = attackSplit[1]
            attack = []
            attack.append(attacker(name=SCOUT,x=scoutPos[0],y=scoutPos[1],num=scoutNum))
            attack.append(attacker(name=DEMOLISHER,x=demoPos[0],y=demoPos[1],num=demoNum))
            attack_set_list.append(attack)
        return attack_set_list
    
    def estimate_our_demo_placement(self, game_state):
        validAttackPos = []
        leftDev = 10000
        rightDev = 10000
        validLeftPos = []
        validRightPos = []
        leftFound = False
        rightFound = False
        #Left side
        initLeft = [6,7]
        initRight = [21,7]
        for offset in range(7):

            if leftFound is False:
                for side in range(2): #side = 0 means towards bottom, side=1 looks towards top
                    sideToggle = pow(-1, side)
                    testLeftPos = [initLeft[0]-offset*sideToggle , initLeft[1]- offset*sideToggle]
                    if self.verbose: gamelib.debug_write(testLeftPos)
                    if (game_state.contains_stationary_unit(testLeftPos) is False):
                        unitPath = game_state.find_path_to_edge(testLeftPos)
                        if(unitPath[-1][1]>=14):
                            validLeftPos.append(testLeftPos)
                            leftDev = offset
                            leftFound = True
            if rightFound is False:
                for side in range(2): #side = 0 means towards bottom, side=1 looks towards top
                    sideToggle = pow(-1, side)
                    testRightPos = [initRight[0]+offset*sideToggle, initRight[1]+offset*sideToggle]
                    if self.verbose: gamelib.debug_write(testRightPos)
                    if (game_state.contains_stationary_unit(testRightPos) is False):
                        unitPath = game_state.find_path_to_edge(testRightPos)
                        if(unitPath[-1][1]>=14):
                            validRightPos.append(testRightPos)
                            rightDev = offset
                            rightFound = True
        
        #Check that we found some valid attack position
        if (not (leftFound or rightFound)):
            return None
        #After finding "valid" start positions for interceptors, we pick one of them
        if leftDev < 10 and (leftDev <= rightDev):
            validAttackPos.append(random.choice(validLeftPos))
        if rightDev < 10 and (rightDev <= leftDev):
            validAttackPos.append(random.choice(validRightPos))
        
        return random.choice(validAttackPos)

    def get_our_scout_demo_split(self, game_state): #TODO
        #Returns two positions, first is scout and second is for demo. Checks path length of all start positions and checks shortest and longest ones
        initPositions = [[13,0],[14,0]]
        validPaths = []

        for y in range(14):
            for i in range(2):
                #gamelib.debug_write(initPositions)
                translationSign = pow(-1,i)
                testPos = [initPositions[i][0]-y*translationSign,initPositions[i][1]+y]
                if(game_state.contains_stationary_unit(testPos) is False): #Check location is spawnable
                    unitPath = game_state.find_path_to_edge(testPos)
                    #gamelib.debug_write(unitPath)
                    #gamelib.debug_write(unitPath[-1])
                    if(unitPath[-1][1] >= 14): #Check that this path ends on our side or on their last line
                        newPath = [testPos, len(unitPath)]
                        validPaths.append(newPath)
        if self.verbose: gamelib.debug_write(validPaths)
        if len(validPaths)==0:
            return None
        #We've now got the starting point and length of each path to our side, we'll find the minimum/max of these and pick one at random for scout/demo
        minPathLength = 10000
        maxPathLength = -1
        validScoutPaths = []
        validDemoPaths = []
        for path in validPaths:
            if (path[1] < minPathLength):
                minPathLength = path[1]
                validDemoPaths = []
                validDemoPaths.append(path[0])
            elif (path[1] == minPathLength):
                validDemoPaths.append(path[0])
            
            if (path[1] > maxPathLength):
                maxPathLength = path[1]
                validScoutPaths = []
                validScoutPaths.append(path[0])
            elif (path[1] == maxPathLength):
                validScoutPaths.append(path[0])
        #All paths in valid scoutpaths and validdemopaths are the same length, so we just pick a random start position amongst them and send that off.
        if self.verbose: gamelib.debug_write(validScoutPaths)
        if self.verbose: gamelib.debug_write(validDemoPaths)
        if  float(maxPathLength) <= 1.6 * float(minPathLength):
            return None
        spawnPositions = [random.choice(validScoutPaths), random.choice(validDemoPaths)]
        return spawnPositions

    def roll_out_our_attack_sets(self, game_state, attack_set_list):

        # List of attack sets, we then run each in a simulation to see which states they generate.

        '''
        args: game_state: GameState
              attack_set_list: List[List[Attacker]]
        returns: None if no attack was deemed good enough, otherwise: List[Attack]
        '''


        gamelib.debug_write("Attack list: {}".format(attack_set_list))

        # Start the timer.
        start_time = time.time()

        # Get the attack set list.
        sim = Simulator(game_state, self.config)

        current_best_score = -1000
        index_best_score = None

        # Loop through the list and update.
        for i in range(len(attack_set_list)):
            if self.verbose: gamelib.debug_write('Time elapsed: {}'.format(time.time() - start_time))
            if time.time() - start_time > 0.75:
                # Too much time taken.
                break
            roll_out_score = sim.roll_out_one_turn(attack_set_list[i], [], [], [])
            gamelib.debug_write("Simulation iteration: {}. Attacker List: {}. Score: {}".format(i, attack_set_list[i], roll_out_score))

            # Want to look at both the score and the end states.
            if sim.simulated_game_state.enemy_health < 0:
                gamelib.debug_write("Amount of enemy health: {}. Below zero so returning as the best attack list: {}".format(sim.simulated_game_state.game_state_info["enemy_health"], attack_set_list[i]))
                # This is a knock out blow, so return this.
                return attack_set_list[i]

            gamelib.debug_write("Amount of enemy_health after sim: {}  Amount before: {}".format(sim.simulated_game_state.game_state_info["enemy_health"], game_state.enemy_health))
            if sim.simulated_game_state.game_state_info["enemy_health"] - game_state.enemy_health < -0.5:
                gamelib.debug_write("Good enough to use as an attack. Score: {}".format(roll_out_score))
                if roll_out_score > current_best_score:
                    index_best_score = i
                    current_best_score = roll_out_score
            
            sim.reset()

        if index_best_score is not None:
            # We found a good enough attack so send this.
            gamelib.debug_write("Best attack found and is good enough. Attack: {}".format(attack_set_list[index_best_score]))
            return attack_set_list[index_best_score]
        else:
            return None




    def place_and_remove_blocking_wall(self, game_state):
        if self.verbose: gamelib.debug_write("MOVING WALL")
        if self.blocking_wall_placement != "CENTER":
            # We need to alternate side to side.
            if self.blocking_wall_placement == "LEFT":
                # Wall is currently at [6, 10]
                # Attempt to build here, and set blocking_wall to right.
                game_state.attempt_spawn(WALL, locations=[6, 10])
                # Attempt to remove
                game_state.attempt_remove(locations=[6, 10])
                self.blocking_wall_placement = "RIGHT"
            else:
                game_state.attempt_spawn(WALL, locations=[21, 10])
                game_state.attempt_remove(locations=[21, 10])
                self.blocking_wall_placement = "LEFT"
        else:
            # We can pass so long as we haven't built either.
            if game_state.contains_stationary_unit([6, 10]):
                self.blocking_wall_placement = "LEFT"
            if game_state.contains_stationary_unit([21, 10]):
                self.blocking_wall_placement = "RIGHT"


    # Place walls and turrets once the p_queue is empty.
    def continue_placing_walls_and_turrets(self, game_state):
        ''' 
        This function should only be called when 
        a) Not thor's hammering
        b) Once p_queue is empty and have left over credit.
        Places them directly from within here.
        '''
        # Pick left and right placement by whether off or even turn.
        if game_state.turn_number % 2 == 0:
            mean_x, mean_y = 9, 18
        else:
            mean_x, mean_y = 18, 11

        # Record time just to make sure we don't run too long.
        start_time = time.time()
        while(game_state.get_resource(MP, player_index=0) > 2 and time.time() - start_time < 0.25):
            if self.verbose: gamelib.debug_write("Time elapsed since starting to place extra troops: {}".format(time.time() - start_time))

            # Sample a location. Var grows with time. # DAVID / HENRY thoughts? 
            x = int(random.gauss(mean_x, 3 + game_state.turn_number * 0.1))
            y = int(random.gauss(mean_y, 3 + game_state.turn_number * 0.1))

            if game_state.game_map.in_arena_bounds([x, y]) and self.can_place.get((x,y), True):
                if game_state.can_spawn(TURRET, [x, y]):
                    if random.random() > 0.3:
                        game_state.attempt_spawn(TURRET, [x, y])
                    else:
                        game_state.attempt_spawn(WALL, [x, y])
                elif len(game_state.game_map[x, y]) == 1:
                    # Then attempt to upgrade what is already there.
                    game_state.attempt_upgrade([x, y])
                else:
                    if self.verbose: gamelib.debug_write("Could not place at ({}, {})".format(x, y))
        

    def inital_add_to_p_queue(self, game_state):
        
        # Round 0
        inital_turrets = [[3, 12], [24, 12], [7, 8], [20, 8]]
        inital_walls = [[3, 13], [24, 13], [7, 9], [20, 9]]
        self.critical_turrets_non_hammer += inital_turrets
        self.crtical_walls_non_hammer += inital_walls

        # Round 1
        for index, turret in enumerate(inital_turrets):
            self.p_queue.put((-1 + int(index) * 0.01, building(name=TURRET, x=turret[0], y=turret[1])))
            self.p_queue.put((-1 + int(index) * 0.015, building(name='upgrade', x=turret[0], y=turret[1])))
        for wall in inital_walls:
            self.p_queue.put((-0.9, building(name=WALL, x=wall[0], y=wall[1])))

        # Round 3
        next_walls = [[0, 13], [1, 13], [2, 13], [25, 13], [26, 13], [27, 13]]
        self.crtical_walls_non_hammer += [[2, 13], [25, 13]]
        self.critical_walls_hammer += [[0, 13], [1, 13], [26, 13], [27, 13]]
        for wall in next_walls:
            self.p_queue.put((-0.8, building(name=WALL, x=wall[0], y=wall[1])))

        next_turrets = [[4, 11], [23, 11]]
        self.critical_turrets_non_hammer += next_turrets
        for index, turret in enumerate(next_turrets):
            self.p_queue.put((-0.7 + int(index) * 0.01, building(name=TURRET, x=turret[0], y=turret[1])))
            self.p_queue.put((-0.7 + int(index) * 0.015, building(name='upgrade', x=turret[0], y=turret[1])))
        
        next_walls = [[4, 12], [23, 12], [5, 11], [22, 11]]
        self.crtical_walls_non_hammer += next_walls
        for wall in next_walls:
            self.p_queue.put((-0.65, building(name=WALL, x=wall[0], y=wall[1])))
        
        next_turrets = [[6, 9], [21, 9], [11, 4], [16, 4]]
        self.critical_turrets_non_hammer += next_turrets
        for turret in next_turrets:
            self.p_queue.put((-0.6, building(name=TURRET, x=turret[0], y=turret[1])))
        
        next_walls = [[8, 8], [19, 8], [11, 5], [16, 5]]
        self.crtical_walls_non_hammer += next_walls
        for wall in next_walls:
            self.p_queue.put((-0.55, building(name=WALL, x=wall[0], y=wall[1])))

        # Upgrade those next_turrets
        for turret in next_turrets[0:2]:
            self.p_queue.put((-0.5, building(name='upgrade', x=turret[0], y=turret[1])))

        next_turrets = [[1, 12], [26, 12], [8, 7], [2, 12], [25, 12], [19, 7]] 
        self.critical_turrets_hammer += [[1, 12], [2, 12], [25, 12], [26, 12]]
        self.critical_turrets_non_hammer += [[8, 7], [19, 7]]
        for turret in next_turrets:
            self.p_queue.put((-0.45, building(name=TURRET, x=turret[0], y=turret[1])))

        next_walls = [[9, 7], [18, 7], [10, 6], [17, 6], [12, 4], [13, 4], [14, 4], [15, 4], [6, 10]]
        self.crtical_walls_non_hammer += [[9, 7], [18, 7], [10, 6], [17, 6], [12, 4], [13, 4], [14, 4], [15, 4]]
        for wall in next_walls:
            self.p_queue.put((-0.4, building(name=WALL, x=wall[0], y=wall[1])))

        for turret in next_turrets:
            self.p_queue.put((-0.35, building(name='upgrade', x=turret[0], y=turret[1])))
        for wall in [[0, 13], [1, 13], [26, 13], [27, 13] , [2, 13], [25, 13]]:
            self.p_queue.put((-0.35, building(name='upgrade', x=wall[0], y=wall[1])))

        supports = [[12, 3], [13, 3], [14, 3], [15, 3]]
        self.critical_supports_non_hammer += supports
        for supp in supports:
            self.p_queue.put((-0.3, building(name=SUPPORT, x=supp[0], y=supp[1])))

            
        extra_turrets = [[22, 12], [6, 11], [20, 10], [8, 9]]
        self.critical_turrets_non_hammer += extra_turrets
        for turret in extra_turrets:
            self.p_queue.put((-0.25, building(name=TURRET, x=turret[0], y=turret[1])))

        extra_supports = [[13, 2], [14, 2]]
        self.critical_supports_non_hammer += extra_supports
        for supp in extra_supports:
            self.p_queue.put((-0.225, building(name=SUPPORT, x=supp[0], y=supp[1])))


        extra_walls = [[21, 12], [7, 11], [19, 11], [9, 10], [19, 10], [9, 9]]
        self.crtical_walls_non_hammer += extra_walls
        for wall in next_walls:
            self.p_queue.put((-0.2, building(name=WALL, x=wall[0], y=wall[1])))

        for turr in extra_turrets:
            self.p_queue.put((-0.15, building(name='upgrade', x=turr[0], y=turr[1])))


        # Upgrade the walls and turrets near the front
        walls_to_upgrade = [[3, 13], [24, 13], [7, 9], [20, 9]]
        for wall in walls_to_upgrade:
            self.p_queue.put((-0.15, building(name='upgrade', x=wall[0], y=wall[1])))

        

    def queue_repair_of_critical(self, game_state):

        current_stationary_units = self.get_current_stationary_units(game_state)
        if not self.thunder_striking:
            walls = self.critical_walls_hammer + self.crtical_walls_non_hammer
            turrets = self.critical_turrets_hammer + self.critical_supports_non_hammer
            supports = self.critical_supports_hammer + self.critical_supports_non_hammer
        else:
            walls = self.crtical_walls_non_hammer
            turrets = self.critical_supports_non_hammer
            supports = self.critical_supports_non_hammer

        # Loop through the critical objects, if we cannot find then 
        for item in walls:
            if building(name=WALL, x=item[0], y=item[1]) not in current_stationary_units and self.defence_priority_map.get(building(name=WALL, x=item[0], y=item[1]), False):
                # Look for it in the map.
                if self.verbose: gamelib.debug_write(self.defence_priority_map)
                value = self.defence_priority_map.get(building(name=WALL, x=item[0], y=item[1]), 0)
                if self.verbose: gamelib.debug_write("Placing back into prioity queue: {}".format(value))
                self.p_queue.put((value, building(name=WALL, x=item[0], y=item[1])))

        for item in turrets:
            if building(name=TURRET, x=item[0], y=item[1]) not in current_stationary_units and self.defence_priority_map.get(building(name=TURRET, x=item[0], y=item[1]), False):
                value = self.defence_priority_map.get(building(name=TURRET, x=item[0], y=item[1]), 0)
                if self.verbose: gamelib.debug_write("Placing back into prioity queue: {}".format(value))
                self.p_queue.put((value, building(name=TURRET, x=item[0], y=item[1])))
                self.p_queue.put((value, building(name='upgrade', x=item[0], y=item[1])))

        for item in supports:
            if building(name=SUPPORT, x=item[0], y=item[1]) not in current_stationary_units and self.defence_priority_map.get(building(name=SUPPORT, x=item[0], y=item[1]), False):
                value = self.defence_priority_map.get(building(name=SUPPORT, x=item[0], y=item[1]), 0)
                if self.verbose: gamelib.debug_write("Placing back into prioity queue: {}".format(value))
                self.p_queue.put((value, building(name=SUPPORT, x=item[0], y=item[1])))


    def get_current_stationary_units(self, game_state):
        '''
        returns a list of our stationary units in the form [type, [location_x, location_y]]
        Used for keeping track of what was destroyed in the previous round
        '''
        stationary_units = set()
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 0:
                        stationary_units.add((unit.unit_type, location[0], location[1]))
        return stationary_units


    def build_queued_defences(self, game_state):
        number_placed = 1
        should_be_able_to_place = True
        # Takes what on p queue.
        while(not self.p_queue.empty() and game_state.get_resource(resource_type=SP, player_index=0) > 0):
            defence_value, defence = self.p_queue.get()        # building object
            if self.verbose: gamelib.debug_write("Popped off the queue: P_Value: {}  Item: {}".format(defence_value, defence))

            # Get the cost of the object if this is greater than the amount of SP points, then place back onto the queue and break.
            # Add this to the dictionary of defences to prioities.
            self.defence_priority_map[defence] = defence_value

            # Need to careful here whether we decide to upgrade or build a new defence.
            if(defence.name == 'upgrade'):
                # First check there is something there to upgrade.
                if game_state.game_map[defence.x, defence.y] != []:
                    # should_be_able_to_place = True
                    if(game_state.type_cost(unit_type=game_state.game_map[defence.x, defence.y][0].unit_type, upgrade=True)[0] > game_state.get_resource(resource_type=SP, player_index=0)):
                        # We cannot afford place back onto the queue and break.
                        self.p_queue.put((defence_value, defence))
                        break
                    else:
                        number_placed = game_state.attempt_upgrade([defence.x, defence.y])
                else:
                    # Need to queue the building first with high prioity.
                    self.p_queue.put((defence_value - 0.01, building(name=TURRET, x=defence.x, y=defence.y)))
            else: 
                if(game_state.type_cost(unit_type=defence.name)[0] > game_state.get_resource(resource_type=SP, player_index=0)):
                    self.p_queue.put((defence_value, defence))
                    break
                else:
                    should_be_able_to_place = game_state.can_spawn(defence.name, [defence.x, defence.y])
                    number_placed = game_state.attempt_spawn(defence.name, [defence.x, defence.y])
                    if(number_placed==0 and should_be_able_to_place):
                        self.p_queue.put((defence_value, defence))
                        gamelib.debug_write("An error has occured here, where we should have been able to place and had credit but didn't. If so break the loop.")
                        break

            if self.verbose: gamelib.debug_write('Attempting to spawn {} at location ({}, {}). Number placed: {}'.format(defence.name, defence.x, defence.y, number_placed))



    def place_attackers(self, game_state, attacker_list):
        '''
        attacker_list: List[Attacker] where Attacker is the usual named_tuple.
        attacker = namedtuple('Attacker', ['name', 'x', 'y', 'num'])
        '''

        for att in attacker_list:
            game_state.attempt_spawn(att.name, [att.x, att.y], att.num)


    def find_oppo_best_strategy_and_interceptor_response(self, game_state):
        ''' 
        args: game_state: GameState should have been copied already.
        returns: List[attacker] - best placement of interceptors.
        '''
        start_time = time.time()

        # Update using the prioity queue
        self.update_game_state_while_p_queue_unloading(game_state)
        gamelib.debug_write("Time elapsed after updating game state: {}".format(time.time() - start_time))

        start_time = time.time()        

        # Get possible attacks for oppo
        oppo_attack_set = self.prepare_attack_sets_for_oppo_during_first_stage(game_state)
        gamelib.debug_write("Oppo Attack Set: {}".format(oppo_attack_set))
        gamelib.debug_write("Time elapsed after finding oppo attack set: {}".format(time.time() - start_time))
        

        if len(oppo_attack_set) == 0:
            return None

        start_time = time.time()

        # Find their best attack
        best_oppo_attack, unintercepted_score = self.find_oppo_best_attack_no_interceptors(game_state, oppo_attack_set)
        gamelib.debug_write("Best attack from the oppo: {} with score: {}".format(best_oppo_attack, unintercepted_score))
        gamelib.debug_write("Time elapsed after finding best oppo attack: {}".format(time.time() - start_time))

        start_time = time.time()

        # Get our possible interceptor placements based on the number of credits the oppo have.
        our_interceptor_attacks = self.prepare_our_interceptors_to_respond(game_state)
        gamelib.debug_write("Our possible interceptor responcses: {}".format(our_interceptor_attacks))
        gamelib.debug_write("Time elapsed after getting our interceptor placements: {}".format(time.time() - start_time))

        start_time = time.time()

        our_best_attack, interupted_score = self.find_our_best_response(game_state, best_oppo_attack, our_interceptor_attacks)
        gamelib.debug_write("Best interceptors: {}   with score: {}".format(our_best_attack, interupted_score))
        gamelib.debug_write("Time elapsed after finding our best response: {}".format(time.time() - start_time))

        return our_best_attack


    def update_game_state_while_p_queue_unloading(self, game_state):

        # Copy the p_queue.
        copied_p_queue = PriorityQueue()
        for i in self.p_queue.queue: 
            copied_p_queue.put(i)

        if self.verbose: gamelib.debug_write("Original P Queue: {}".format(self.p_queue.queue))
        if self.verbose: gamelib.debug_write("New P Queue: {}".format(copied_p_queue.queue))


        # Add to the defender list till we run out of credit.
        while(not copied_p_queue.empty() and game_state.get_resource(resource_type=SP, player_index=0) > 0):

            _, defence = copied_p_queue.get()

            if(defence.name == 'upgrade'):
                should_be_able_to_place = True
                number_placed = game_state.attempt_upgrade([defence.x, defence.y])
            else: 
                should_be_able_to_place = game_state.can_spawn(defence.name, [defence.x, defence.y])
                number_placed = game_state.attempt_spawn(defence.name, [defence.x, defence.y])
            
            if(number_placed==0 and should_be_able_to_place):
                break
        # Game state should now contain as many elements as we can place ready to look at what attacks could be thrown.
        if self.verbose: gamelib.debug_write("After adding our next p queue elements")
        if self.verbose: self.print_map(game_state)



    def prepare_attack_sets_for_oppo_during_first_stage(self, game_state):

        # This will take in the game state from the updated_game_state_while... function which will have added what we would do in the next round.
        # We can then prepare some attckers and check whether they are feasible.

        # TODO - Need to prep for the oppo actual defences.

        # DAVID / HENRY LOOK

        oppo_mp = int(game_state.get_resource(resource_type=MP, player_index=1))
        if self.verbose: gamelib.debug_write("Opponent MP :" + str(oppo_mp))
        attack_set_list = [] #Create an empty list of possible attacks

        #For now calculate opponent attack sets in three cases determined by their MP. MP <= 10, 10 < MP <= 20, MP >20 
        if(oppo_mp <= 10): 
            #Case 1: Scout Rush
            scoutPos = self.get_scout_attack_position(game_state)
            if scoutPos is not None:
                attack_set_list.append([attacker(name=SCOUT, x=scoutPos[0],y=scoutPos[1],num=oppo_mp)])

            #Case 2: Split Scout (Enemy Thor) TODO later

            #Case 3: Full Demo Rush
            demoPos = self.get_enemy_demo_attack_position(game_state)
            if demoPos is not None:
                attack_set_list.append([attacker(name=DEMOLISHER,x=demoPos[0],y=demoPos[1],num=int(math.floor(oppo_mp/3)))])  

            #Case 4: Scout-Demo Split REMOVED due to time
            # if(oppo_mp >= 4):
            #     splitPositions = self.get_scout_demo_split_positions(game_state)
            #     if splitPositions is not None:
            #         splitNumbers = self.get_enemy_scout_demo_split_numbers(oppo_mp)
            #         scout_demo_attack = []
            #         scout_demo_attack.append(attacker(name=SCOUT, x= splitPositions[0][0],y=splitPositions[0][1],num=splitNumbers[1]))
            #         scout_demo_attack.append(attacker(name=DEMOLISHER, x= splitPositions[1][0], y=splitPositions[1][1], num=splitNumbers[0]))
            #         attack_set_list.append(scout_demo_attack)
            
            #Case 5: Cheeky Interceptors NOTE will assume central placement for now but it's a lot more complicated than that in reality
            if self.verbose: gamelib.debug_write("INTERCEPTOR CASE")
            interceptorPos = self.estimate_enemy_interceptor_position(game_state)
            if self.verbose: gamelib.debug_write(interceptorPos)
            if interceptorPos is not None:
                attack_set_list.append([attacker(name=INTERCEPTOR, x=interceptorPos[0],y=interceptorPos[1],num=oppo_mp)])

        elif (oppo_mp > 10 and oppo_mp <= 20): #MP between 10 and 21, so mid-range attack
            #Case 1: Big Scout Rush
            scoutPos = self.get_scout_attack_position(game_state)
            if scoutPos is not None:
                attack_set_list.append([attacker(name=SCOUT, x=scoutPos[0],y=scoutPos[1],num=oppo_mp)])
            demoPos = scoutPos
            #Case 2 Split Scout (Enemy Thor)
            
            #Case 3 All Demo attack NOTE will assume same position as scout attack case for now but might change
            
            if demoPos is not None:
                attack_set_list.append([attacker(name=DEMOLISHER,x=demoPos[0],y=demoPos[1],num=int(math.floor(oppo_mp/3)))])  

            #Case 4 Scout-Demo split (only do if at least 4 credits)
            # splitPositions = self.get_scout_demo_split_positions(game_state) #Calc best starting points for each unit
            # if splitPositions is not None:
            #     splitNumbers = self.get_enemy_scout_demo_split_numbers(oppo_mp) #Calc split based on credits
            #     scout_demo_attack = []
            #     scout_demo_attack.append(attacker(name=SCOUT, x= splitPositions[0][0],y=splitPositions[0][1],num=splitNumbers[1]))
            #     scout_demo_attack.append(attacker(name=DEMOLISHER, x= splitPositions[1][0], y=splitPositions[1][1], num=splitNumbers[0]))
            #     attack_set_list.append(scout_demo_attack)


        else: # MP >20 big fucko wucko attack
            #Case 1: Scary Enemy Thor

            #Case 2: Big Scout Rush (one stack)
            scoutPos = self.get_scout_attack_position(game_state)
            if scoutPos is not None:
                attack_set_list.append([attacker(name=SCOUT, x=scoutPos[0],y=scoutPos[1],num=oppo_mp)])

            #Case 3: Big Demo Rush
            demoPos = scoutPos
            if demoPos is not None:
                attack_set_list.append([attacker(name=DEMOLISHER,x=demoPos[0],y=demoPos[1],num=int(math.floor(oppo_mp/3)))])  

            # #Case 4: Scout-Demo Split
            # splitPositions = self.get_scout_demo_split_positions(game_state) #Calc best starting points for each unit
            # if splitPositions is not None:
            #     splitNumbers = self.get_enemy_scout_demo_split_numbers(oppo_mp) #Calc split based on credits
            #     scout_demo_attack = []
            #     scout_demo_attack.append(attacker(name=SCOUT, x= splitPositions[0][0],y=splitPositions[0][1],num=splitNumbers[1]))
            #     scout_demo_attack.append(attacker(name=DEMOLISHER, x= splitPositions[1][0], y=splitPositions[1][1], num=splitNumbers[0]))
            #     attack_set_list.append(scout_demo_attack) #Send attack

        if self.verbose: gamelib.debug_write("Opponent Attack sets: "+ str(attack_set_list))
        return attack_set_list

    def estimate_enemy_interceptor_position(self, game_state): #Returns a list of coordinate and number pairs for interceptor spawns + 
        validAttackPos = []
        leftDev = 10000
        rightDev = 10000
        validLeftPos = []
        validRightPos = []
        leftFound = False
        rightFound = False
        #Left side
        initLeft = [6,20]
        initRight = [21,20]
        for offset in range(7):
            if leftFound is False:
                for side in range(2): #side = 0 means towards bottom, side=1 looks towards top
                    sideToggle = pow(-1, side)
                    testLeftPos = [initLeft[0]-offset*sideToggle , initLeft[1]- offset*sideToggle]
                    if self.verbose: gamelib.debug_write(testLeftPos)
                    if self.verbose: gamelib.debug_write(testLeftPos)
                    if (game_state.contains_stationary_unit(testLeftPos) is False):
                        unitPath = game_state.find_path_to_edge(testLeftPos)
                        if(unitPath[-1][1]<=14):
                            validLeftPos.append(testLeftPos)
                            leftDev = offset
                            leftFound = True
            if rightFound is False:
                for side in range(2): #side = 0 means towards bottom, side=1 looks towards top
                    sideToggle = pow(-1, side)
                    testRightPos = [initRight[0]+offset*sideToggle, initRight[1]+offset*sideToggle]
                    if self.verbose: gamelib.debug_write(testRightPos)
                    if self.verbose: gamelib.debug_write(testRightPos)
                    if (game_state.contains_stationary_unit(testRightPos) is False):
                        unitPath = game_state.find_path_to_edge(testRightPos)
                        if(unitPath[-1][1]<=14):
                            validRightPos.append(testRightPos)
                            rightDev = offset
                            rightFound = True
        
        #Check that we found some valid attack position
        if (not (leftFound or rightFound)):
            return None
        #After finding "valid" start positions for interceptors, we pick one of them
        if leftDev < 10 and (leftDev <= rightDev):
            validAttackPos.append(random.choice(validLeftPos))
        if rightDev < 10 and (rightDev <= leftDev):
            validAttackPos.append(random.choice(validRightPos))
        
        return random.choice(validAttackPos)
        

    #TODO, possibly implement better heuristic for deciding the attacking side and factor in path of attack, rn we randomly pick left/right

    def get_scout_attack_position(self, game_state): #Try to place an enemy scout rush as close to the top as possible
        initPositions = [[13,27],[14,27]] #Best possible starts on the left and right
        
        validPositions = []
        
        #Start from the very back and basically BFS down
        for y in range(14):
            if len(validPositions) > 0:
                break
            for i in range(2):
                signToggle = pow(-1, i)
                testPos = [initPositions[i][0]-y*signToggle, initPositions[i][1]-y]
                if (game_state.contains_stationary_unit(testPos) is False): #Check if position is occupied if not, then we pick here
                    unitPath = game_state.find_path_to_edge(initPositions[i]) #Also get the path of this attack
                    if(unitPath[-1][1] <= 14): #Check the attack actually ends on our side or on their last line (Kamikaze into our walls)
                        validPositions.append(testPos)

        if len(validPositions) == 0:
             return None
        #After this point, first element of finalPositions is the "best" left attack, and the other is the "best" right attack
        return random.choice(validPositions) #Coin flip the attack side for now

    def get_enemy_demo_attack_position(self, game_state): #Try to place an enemy scout rush as close to the top as possible
        initPositions = [[13,27],[14,27]] #Best possible starts on the left and right
            
        validPositions = []
            
        #Start from the very back and basically BFS down
        for y in range(14):
            if len(validPositions) > 0:
                break
            for i in range(2):
                signToggle = pow(-1, i)
                testPos = [initPositions[i][0]-y*signToggle, initPositions[i][1]-y]
                if (game_state.contains_stationary_unit(testPos) is False): #Check if position is occupied if not, then we pick here
                    unitPath = game_state.find_path_to_edge(initPositions[i]) #Also get the path of this attack
                    if(unitPath[-1][1] <= 14): #Check the attack actually ends on our side or on the max range of a Demo
                        validPositions.append(testPos)

        if len(validPositions) == 0:
            return None
        #After this point, first element of finalPositions is the "best" left attack, and the other is the "best" right attack
        return random.choice(validPositions) #Coin flip the attack side for now


    #NOTE QUESTION, does the find path to edge take into account walls that will be destroyed in the coming turn? If not this becomes a bit messy?
    def get_scout_demo_split_positions(self, game_state):
        #Returns two positions, first is scout and second is for demo. Checks path length of all start positions and checks shortest and longest ones
        initPositions = [[13,27],[14,27]]
        validPaths = []

        for y in range(14):
            for i in range(2):
                #gamelib.debug_write(initPositions)
                translationSign = pow(-1,i)
                testPos = [initPositions[i][0]-y*translationSign,initPositions[i][1]-y]
                if(game_state.contains_stationary_unit(testPos) is False): #Check location is spawnable
                    unitPath = game_state.find_path_to_edge(testPos)
                    #gamelib.debug_write(unitPath)
                    #gamelib.debug_write(unitPath[-1])
                    if(unitPath[-1][1] <= 14): #Check that this path ends on our side or on their last line
                        newPath = [testPos, len(unitPath)]
                        validPaths.append(newPath)
        if self.verbose: gamelib.debug_write(validPaths)
        if len(validPaths)==0:
            return None
        #We've now got the starting point and length of each path to our side, we'll find the minimum/max of these and pick one at random for scout/demo
        minPathLength = 10000
        maxPathLength = -1
        validScoutPaths = []
        validDemoPaths = []
        for path in validPaths:
            if (path[1] < minPathLength):
                minPathLength = path[1]
                validDemoPaths = []
                validDemoPaths.append(path[0])
            elif (path[1] == minPathLength):
                validDemoPaths.append(path[0])
            
            if (path[1] > maxPathLength):
                maxPathLength = path[1]
                validScoutPaths = []
                validScoutPaths.append(path[0])
            elif (path[1] == maxPathLength):
                validScoutPaths.append(path[0])
        #All paths in valid scoutpaths and validdemopaths are the same length, so we just pick a random start position amongst them and send that off.
        if self.verbose: gamelib.debug_write(validScoutPaths)
        if self.verbose: gamelib.debug_write(validDemoPaths)
        spawnPositions = [random.choice(validScoutPaths), random.choice(validDemoPaths)]
        return spawnPositions

    #Retrieves the numbers in the split for scouts and demolishers, first number is for demos and second is for scouts.
    def get_enemy_scout_demo_split_numbers(self, enemy_mp): #This assumes enemy_mp >= 4

        enemy_mp = int(math.floor(enemy_mp)) #Going to round down to use a fat list for all cases from 4 <= mp < 20
        if(enemy_mp >= 21):
            d = math.floor((enemy_mp-1)/5)
            return ([d-1, 3*(d-1)])
        if(enemy_mp == 20):
            return ([4,8]) if random.randint(0,1)==1 else ([5,5])
        scout_demo_split = [[1,1], [1,2], [1,3], [1,4], [1,5], [2,3], [2,4], [2,5], [2,6], [2,7], [3,5], [3,6], [3,7], [4,5], [4,6], [4,7], [4,8]] #I pray this is right
        return scout_demo_split[enemy_mp-4]







    def find_oppo_best_attack_no_interceptors(self, game_state, attack_sets):
        ''' 
        Needs to be a copied game state object
        args: game_state: - GameState object.
        returns: [List[List[attacker]], float]        this is the list of attackers which was the best play.
        '''

        # Start the timer.
        start_time = time.time()

        # Get the attack set list.
        sim = Simulator(game_state, self.config)

        current_worst_score = 1000
        index_worst_score = 0

        # Loop through the list and update.
        for i in range(len(attack_sets)):
            gamelib.debug_write('Time elapsed: {}'.format(time.time() - start_time))
            if time.time() - start_time > 0.75:
                # Too much time taken.
                break
            roll_out_score = sim.roll_out_one_turn([], attack_sets[i], [], [])
            gamelib.debug_write("Simulation iteration: {}. Attacker List: {}. Score: {}".format(i, attack_sets[i], roll_out_score))

            # Update if needed
            if roll_out_score < current_worst_score:
                current_worst_score = roll_out_score
                index_worst_score = i

            sim.reset()
        
        if self.verbose: gamelib.debug_write("Returing as oppo best attack: {}     because of score {}".format(attack_sets[index_worst_score], current_worst_score))
        return [attack_sets[index_worst_score], current_worst_score]


    def prepare_our_interceptors_to_respond(self, game_state):

        oppo_mp = game_state.get_resource(resource_type=MP, player_index=1)
        our_mp = game_state.get_resource(resource_type=MP, player_index=1)

        if oppo_mp <= 9 or our_mp == 1:
            # Then we can either place on the left, middle or right.
            # 1 interceptors
            return [[attacker(name=INTERCEPTOR, x=18, y=4, num=1)], 
                [attacker(name=INTERCEPTOR, x=7, y=6, num=1)], 
                [attacker(name=INTERCEPTOR, x=14, y=0, num=1)]]
        elif oppo_mp <= 16 or our_mp == 2:
            # 2 interceptors
            return [[attacker(name=INTERCEPTOR, x=7, y=6, num=1), attacker(name=INTERCEPTOR, x=20, y=6, num=1)], 
            [attacker(name=INTERCEPTOR, x=14, y=0, num=2)],
            [attacker(name=INTERCEPTOR, x=13, y=0, num=2)]]
        else:
            # 3 interceptors
            return [[attacker(name=INTERCEPTOR, x=13, y=0, num=3)],
            [attacker(name=INTERCEPTOR, x=14, y=0, num=3)]]
    

    def find_our_best_response(self, game_state, best_oppo_attack, our_responses):

        start_time = time.time()

        # Get the attack set list.
        sim = Simulator(game_state, self.config)

        current_best_score = -1000
        index_best_score = 0

        # Loop through the list and update.
        for i in range(len(our_responses)):
            gamelib.debug_write('Time elapsed: {}'.format(time.time() - start_time))
            if time.time() - start_time > 0.75:
                # Too much time taken.
                break
            roll_out_score = sim.roll_out_one_turn(our_responses[i], best_oppo_attack, [], [])
            gamelib.debug_write("Simulation iteration: {}. Interceptor List: {}. Score: {}".format(i, our_responses[i], roll_out_score))

            # Update if needed
            if roll_out_score > current_best_score:
                current_best_score = roll_out_score
                index_best_score = i

            sim.reset()

        if self.verbose: gamelib.debug_write("Returing as our best attack: {}     because of score {}".format(our_responses[index_best_score], current_best_score))
        return [our_responses[index_best_score], current_best_score]




            


    ''' START OF ROLL OUT CODE '''
    ''' OW '''

    # def roll_out_one_turn(self, game_state, our_attacker_list, oppo_attacker_list, our_building_list, oppo_building_list):
    #     ''' 
    #     This will roll out a play give a set of placements of our attackers, our defenders, oppo attackers, oppo defenders
    #     return:
    #         (float, float): my_health, enemy_health
    #     '''

    #     # Can use the can_spawn function.
    #     # Need to ensure that we create new units to place in the game map.

    #     # Create a copy of the game state.
    #     gamelib.debug_write("Beginning roll out")
    #     copied_game_state = copy.deepcopy(game_state)

    #     gamelib.debug_write("Before start of sim")
    #     self.print_map(copied_game_state)
        
    #     # Add the units.
    #     self.add_proposed_units_to_map(copied_game_state, our_attacker_list, oppo_attacker_list, our_building_list, oppo_building_list)

    #     # Set up inital coords and movement paths.
    #     self.set_movement_paths(copied_game_state)

    #     # Simulate turn
    #     self.simulate_one_turn(copied_game_state)

    #     gamelib.debug_write("Finished roll out")
    #     self.print_map(copied_game_state)




    # def add_proposed_units_to_map(self, game_state, our_attacker_list, oppo_attacker_list, our_building_list, oppo_building_list):

    #     # Pass to the helper function.
    #     for att in our_attacker_list:
    #         self.add_single_location_of_units(game_state, 'attacker', att, player_index=0)
    #     for att in oppo_attacker_list:
    #         self.add_single_location_of_units(game_state, 'attacker', att, player_index=1)
    #     for defence in our_building_list:
    #         self.add_single_location_of_units(game_state, 'building', defence, player_index=0)
    #     for defence in oppo_building_list:
    #         self.add_single_location_of_units(game_state, 'building', defence, player_index=1)
        
    
    # def add_single_location_of_units(self, game_state, style, element, player_index):
    #     ''' 
    #     style whether attack or stationary, element is just the tuple and player index 0 / 1 as above. 
    #     This should be a valid allocation based on what the oppo has.
    #     '''
    #     if style == 'attacker':
    #         # This will be an 
    #         # attacker = namedtuple('Attacker', ['name', 'x', 'y', 'num'])
    #         for _ in range(0, element.num):
    #             # Can only add one at a time.
    #             gamelib.debug_write("Doing add of attacker {} to ({}, {})".format(element.name, element.x, element.y))
    #             game_state.game_map.add_unit(unit_type=element.name, location=[element.x, element.y], player_index=player_index)
    #     else:
    #         # building = namedtuple('Building', ['name', 'x', 'y'])
    #         if element.name != 'upgrade':
    #             gamelib.debug_write("Doing add of defender {} to ({}, {})".format(element.name, element.x, element.y))
    #             game_state.game_map.add_unit(unit_type=element.name, location=[element.x, element.y], player_index=player_index)
    #         else:
    #             gamelib.debug_write("Doing upgrade at ({}, {})".format(element.x, element.y))
    #             gamelib.debug_write("Current Unit: {}".format(game_state.game_map[element.x, element.y]))
    #             game_state.game_map[element.x, element.y].upgrade()


        

    # def set_movement_paths(self, game_state):

    #     # After adding the units, run across the game map and set the path for each of units.
    #     # The inital coords will be used for mapping in the future.
    #     for x in range(0,28):
    #         for y in range(0,28):
    #             loc = [x, y]
    #             if game_state.game_map.in_arena_bounds(loc):
    #                 for unit in game_state.game_map[loc]:
    #                     if not unit.stationary:
    #                         # Get the initial path.
    #                         path = game_state.find_path_to_edge(loc)
    #                         # This is a mobile unit so set the path, initial_x, and initial_y
    #                         unit.set_extra_conditions(path=path, x=loc[0], y=loc[1])
    #                     else:
    #                         path = None
    #                         unit.set_extra_conditions(path=path, x=loc[0], y=loc[1])



    # def simulate_one_turn(self, game_state):
    #     ''' 
    #     Pre Condition: Valid board configuation and that "RESTORE" has already happened and "DEPLOY" phase has been simed.
    #     This rolls out one play based on a game state which is in it's final modifed state before the first action frame
    #     return:
    #         GameState: with the game state at the end of the turn from our perspective.
    #     '''
    #     not_done = True
    #     buildings_destroyed = False
    #     current_frame_num = 0
    #     gamelib.debug_write("Simulating one play forward.")
    #     while(current_frame_num < 1000 and not_done):
    #         current_frame_num, not_done, buildings_destroyed = self.simulate_one_action_frame(game_state, current_frame_num, buildings_destroyed)
    #         self.print_map(game_state=game_state)

    #     raise StopIteration


    # def simulate_one_action_frame(self, game_state, frame_num, buildings_destroyed):
    #     ''' 
    #     Pre Condition: Valid board configuation.
    #     Roll out one action frame using the game logic and return this
    #     return: 
    #         GameState: after movements
    #     '''

    #     # To hold the new values 
    #     updated_game_map = gamelib.GameMap(self.config)

    #     gamelib.debug_write("Frame Number: {}".format(frame_num))
    #     gamelib.debug_write("Building Destoryed: {}".format(buildings_destroyed))
        
    #     # Add any health bonuses which I think should be done before. (STAGE 0.)
    #     for loc in game_state.game_map:
    #         if game_state.game_map.in_arena_bounds(loc) and len(game_state.game_map[loc]) == 1 and game_state.game_map[loc][0].unit_type == SUPPORT:
    #             # Get the locations within range:
    #             supported_locations = game_state.game_map.get_locations_in_range(loc, game_state.game_map[loc][0].shieldRange)
    #             for sup_loc in supported_locations:
    #                 for unit in game_state.game_map[sup_loc]:
    #                     if not unit.stationary and not unit.has_been_shielded:
    #                         unit.health += game_state.game_map[loc][0].shieldPerUnit
    #                         gamelib.debug_write("Adding health to unit at location ({}, {})".format(sup_loc[0], sup_loc[1]))

    #     gamelib.debug_write("End of adding health bonuses")
    
    #     # All units take a step if it is their turn. (STAGE 1).
    #     movement = False
    #     troops_alive = False
    #     self_destruct_list = []         # List[x, y] locations for self destruct. Have to be done together as a location.
    #     for loc in [[x,y] for x in range(28) for y in range(28)]:
    #         if game_state.game_map.in_arena_bounds(loc):
    #             # We have at least one unit here, so run through them, and find the target.
    #             for unit in game_state.game_map[loc]:

    #                 # If unit is stationary, then copy onto the new map. Otherwise apply the update logic.
    #                 if unit.stationary:
    #                     updated_game_map.add_existing_unit(unit, location=loc)
    #                 else:
    #                     troops_alive = True
    #                     # Remove the unit from the current location and add to the path.
    #                     if not buildings_destroyed:
    #                         path = unit.current_path
    #                         gamelib.debug_write("Unit at location: ({}, {}) no need to repath.".format(loc[0], loc[1]))
    #                     else:
    #                         # Need to repath the path now.
    #                         unit.current_path = game_state.find_path_based_on_initial(unit)
    #                         path = unit.current_path
    #                         gamelib.debug_write("Unit at location: ({}, {}) repathing.".format(loc[0], loc[1]))

    #                     # Should only move when it is there multiple
    #                     gamelib.debug_write("Unit at location: ({}, {}). Path to end: {}".format(loc[0], loc[1], path))
    #                     gamelib.debug_write("Unit Location: ({}, {}). FrameNum: {}. Speed: {}".format(loc[0], loc[1],frame_num, unit.speed))
    #                     if frame_num == 0 or int(frame_num) % int(1.0 / unit.speed) == 0:
                            
    #                         if loc == path[-1]:
    #                             gamelib.debug_write("Unit at location: ({}, {}) is at the end of the path.".format(loc[0],loc[1]))
    #                             # We are at the end of the path. Either we are at an edge which means we can remove health, or we are in the middle of the board which means we need to self-destruct.
    #                             if unit.player_index == 0 and loc in game_state.game_map.get_edge_locations(game_state.game_map.TOP_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.TOP_RIGHT):
    #                                 # Score on enemy.
    #                                 # game_state.game_map.remove_one_unit(location=[loc[0], loc[1]], unit=unit)
    #                                 game_state.enemy_health -= 1
    #                                 gamelib.debug_write("Removing points from enemy because of unit at location ({}, {})".format(loc[0], loc[1]))
    #                             elif unit.player_index == 1 and loc in game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT):
    #                                 # Score on us.
    #                                 # game_state.game_map.remove_one_unit(location=[loc[0], loc[1]], unit=unit)
    #                                 game_state.my_health -= 1
    #                                 gamelib.debug_write("Removing points from enemy because of unit at location ({}, {})".format(loc[0], loc[1]))
    #                             else:
    #                                 # This is now a self destruct so will need handling.
    #                                 # TODO - These units should be allowed to attack first.
    #                                 gamelib.debug_write("Calling the self destruct logic for location: ({}, {})".format(loc[0], loc[1]))
    #                                 successfully_updated = updated_game_map.add_existing_unit(unit, location=loc)
    #                                 self_destruct_list.append(loc)
    #                         else:
    #                             # Find the next location in the path
    #                             for index, path_loc in enumerate(path):
    #                                 # gamelib.debug_write('Searching for path element matching. Currently {}, looking for {}'.format(path_loc, loc))
    #                                 if path_loc == loc:
    #                                     break

    #                             if index == len(path) - 1:
    #                                 # This signals an error that we could not find a match so throw an error
    #                                 gamelib.debug_write("BIG PROBLMEMMMMMMMMO. Could not find current location in the path which is very bad.")
    #                             else:
    #                                 # Should be able to get next term. No need to check i+1 is valid because above loop would have caught path[-1] == loc.
    #                                 # successfully_removed = updated_game_map.remove_one_unit(location=loc, unit=unit)
    #                                 unit.x, unit.y = path[index+1]
    #                                 # Add to the updated game map.
    #                                 successfully_updated = updated_game_map.add_existing_unit(unit, location=path[index+1])
    #                                 gamelib.debug_write("Updated: {}".format(successfully_updated))
                                    
    #                                 # SHOULD WE REMOVE FROM OUR GAME MAP? 
    #                                 # game_state.game_map.move_unit(unit=unit, location=path[index+1])
    #                                 movement = True
    #                                 gamelib.debug_write("Moved Unit form ({}, {}) old map to ({}, {}) new map".format(loc[0], loc[1], unit.x, unit.y))
    #                     else:
    #                         # None moving piece this turn so just copy over.
    #                         updated_game_map.add_existing_unit(unit, location=loc)

    #     # We now have an updated game_map, so we can use this to perform the attacks.
    #     # Set the new game_map to our game_state.                
    #     game_state.game_map = updated_game_map
    #     buildings_destroyed = False     

    #     # For units in the self-destruct list we can call the logic.
    #     for loc in self_destruct_list:
    #         for unit in game_state.game_map[loc]:
    #             buildings_destroyed = self.self_destruct_logic(game_state, unit, buildings_destroyed)
    #             # Remove this unit from the game_map.
    #             game_state.game_map.remove_one_unit(loc, unit)

        
    #     # Then look at all of the attacks.
    #     # All units attack (STAGE 2).
    #     for loc in game_state.game_map:
    #         if game_state.game_map.in_arena_bounds(loc):
    #             # We have at least one unit here, so run through them, and find the target.
    #             for unit in game_state.game_map[loc]:
    #                 # Find the target
    #                 gamelib.debug_write("Unit currently attacking: {}".format(unit))
    #                 target_unit = game_state.get_target(unit)
    #                 gamelib.debug_write("Target : {}".format(target_unit))
    #                 if target_unit is not None:
    #                     # Remove health from these units picking whether to use the damage to stationary and moving units
    #                     # IMPORTANT: NEED TO REFER TO THESE USING THE UNITS ARE GAME_MAP CAN HAVE MORE THAN ONE ELEMENT IN THE LIST AT EACH LOCATION 
    #                     if(target_unit.stationary):
    #                         target_unit.health -= unit.damage_f
    #                         gamelib.debug_write("Unit at location ({}, {}) firing at target ({}, {}) doing damage {}".format(loc[0], loc[1], target_unit.x, target_unit.y, unit.damage_f))
    #                     else:
    #                         target_unit.health -= unit.damage_i
    #                         gamelib.debug_write("Unit at location ({}, {}) firing at target ({}, {}) doing damage {}".format(loc[0], loc[1], target_unit.x, target_unit.y, unit.damage_i))
                        
    #                     # Remove if health has fallen below zero. (STAGE 3). (techincally in stage 3 but I think it works here)
    #                     if target_unit.health <= 0:
    #                         # Remove from the list.
    #                         # TODO - Check this works, unsure it deffo will.
    #                         game_state.game_map.remove_one_unit(location=[target_unit.x, target_unit.y], unit=target_unit)
    #                         gamelib.debug_write("Removing unit at location ({}, {})".format(loc[0], loc[1]))
    #                         if target_unit.stationary:
    #                             buildings_destroyed = True      # This is to trigger a repathing.


    #     gamelib.debug_write("Finished rolling forward one step.")
    #     gamelib.debug_write("Passing back values. Movement: {}, BuildingDest: {}".format(movement, buildings_destroyed))
    #     # Return with next frame and whether done or not.
    #     return (frame_num + 1, movement or troops_alive, buildings_destroyed)


    # def self_destruct_logic(self, game_state, unit, buildings_destroyed):
    #     '''
    #     Args: 
    #         unit: GameUnit which is self-destructing.
    #     '''
    #     # First need to check that the unit has moved at least 5 squares.
    #     if(abs(unit.x - unit.initial_x) + abs(unit.y - unit.initial_y) >= 5):
    #         damage = unit.max_health * 1.5
    #         damage_locations = game_state.game_map.get_locations_in_range(location=[unit.x, unit.y], radius=1.5)
    #         for loc in damage_locations:
    #             if loc != [unit.x, unit.y]:
    #                 for targeted_unit in game_state.game_map[loc]:
    #                     targeted_unit.health -= damage
    #                     if targeted_unit.health <= 0:
    #                         game_state.game_map.remove_one_unit([targeted_unit.x, targeted_unit.y], targeted_unit)
    #                         buildings_destroyed = True
    #     return buildings_destroyed
                            
       

            
    '''
    Within GameMap: 
        distance_between_locations(loc1, loc2)
        get_location_in_range(loc, radius)

    Within GameState:
        get_target(attacking unit): GameUnit
        get_attackers(location, player_index): List[GameUnit]
        get_target_edge(start_location)
        find_path_to_edge(start_location, target_edge) : List[[x, y]]

    '''



    def print_map(self, game_state):
        gamelib.debug_write('Map:\n')
        for i in range(0,28):
            row_str = "|" 
            for j in range(0,28):
                if game_state.game_map.in_arena_bounds([i,j]):
                    if len(game_state.game_map[i,j]) > 0:
                        row_str += (str(game_state.game_map[i,j][0].player_index) + str(game_state.game_map[i,j][0].unit_type) + " " + str(int(game_state.game_map[i,j][0].health)) + (5-len(str(game_state.game_map[i,j][0].unit_type) + str(game_state.game_map[i,j][0].health))) * " ")
                        # gamelib.debug_write(type(new_state.game_map[i,j][0]))
                    else: 
                        row_str += "       "
                else:
                    row_str += "-------"
            gamelib.debug_write(row_str)









    ''' ------------------------------'''

    # Do not need currently.

    def get_target_for_attacker(self, game_map, attacker_location, player_index):
        '''
        Given the game_map and a location of an attacker find which item will be targeted.
        This depends on the player index, if player_index=0 this is us, player_index=1 is the oppo
        args:
            attacker_location: [x, y]
        return:
            GameUnit: which will be under attack.
        '''

        # Find the radius and damage of the structure at the location.
        attackerRange = game_map[attacker_location].attackRange
        damage_to_mobile_unit = game_map[attacker_location].damage_i
        damage_to_stationary_unit = game_map[attacker_location].damage_f

        # Locations structure could attack.
        possible_attack_locations = game_map.get_location_in_range(attacker_location, attackerRange)

        # Targets that could be attacked in that location.
        possible_targets = []
        for loc in possible_attack_locations:
            for unit in game_map[loc]:
                if unit.player_index != player_index:   
                    possible_targets.append(unit)

        # Put these targets into a list of length 5 for each of the units and then sort on these as this repsects the
        # order of the system. Instead of labels like "mobile" just use 0 and 1. So we sort into ascending order.
        locations_with_orderings = []
        for unit in possible_targets:
            info_about_loc = [unit]
            # Rule 1: Mobile > Stationary. 
            info_about_loc.append(0) if game_map[unit.x, unit.y].stationary else info_about_loc.append(1)
            # Rule 2: Distance
            info_about_loc.append(game_map.distance_between_locations(attacker_location, [unit.x, unit.y]))
            # Rule 3: Health
            info_about_loc.append(game_map[unit.x, unit.y].health)
            # Rule 4: Further down board.
            info_about_loc.append(27 - unit.y) if player_index == 0 else info_about_loc.append(unit.y)
            # Rule 5: Closest to edges
            # CBA for now - come back to. OW - TODO.

        attacker_prioritised_locations = sorted(loc, key = lambda x: (x[1], x[2], x[3], x[4]))  # Will need to entend when add 5.
        target = attacker_prioritised_locations[0]  # Get highest prioity units as an object

        return target



    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units



    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
            damages.append(damage)
        
        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    
    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
