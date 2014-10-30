#!/usr/bin/env python
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# pyre.py
# A Python implementation of a regular expression engine.
#
# See:
# [1] http://ezekiel.vancouver.wsu.edu/~cs317/archive/projects/grep/grep.pdf
# [2] http://swtch.com/~rsc/regexp/regexp1.html
# [3] http://csis.pace.edu/~wolf/CS122/infix-postfix.htm
# [4] http://stackoverflow.com/q/60208/1830334
# [5] http://perl.plover.com/Regex/article.html
# [6] http://www.codeproject.com/Articles/5412/Writing-own-regular-expression-parser#Seven
# -----------------------------------------------------------------------------


import sys
import pdb

from ptr import Ptr
from nfa import State, Frag, Metachar


class Pyre:


    def __init__(self, input_re, debug=False):
        self.debug = debug
        self.operators = {
            '&': 9,
            '|': 8,
            '*': 7,
            '+': 6
        }
        self.list_id = 0
        self.start_ptr = None

        self.__compile(input_re)

  
    def match(self, str):
 
        curr_list_ptr = Ptr([ self.start_ptr ])
        next_list_ptr = Ptr([])

        for char in str:
            self.__step(curr_list_ptr, char, next_list_ptr);
            # We swap lists because on the next iteration of this loop, we need
            # `next_list_ptr` to be the current list of states. We then reuse
            # `curr_list_ptr`.
            temp = curr_list_ptr
            curr_list_ptr = next_list_ptr
            next_list_ptr = temp

        is_a_match = self.__is_match(curr_list_ptr)
        if is_a_match:
            print(self.re_store + ' matches ' + str)
        else:
            print(self.re_store + ' does not match ' + str)


    # TODO: What happens if the client executes `match` twice? Does `start_ptr`
    # need to be reset?
    def __compile(self, input_re):
        """Converts a postfix expression to an NFA and sets the start pointer
        for `match`.

        Args: `re`, an infix expression.

        Returns: void but sets the start pointer for the Pyre instance.
        """

        self.__print('\npyre\n====\n')
        self.__print('compiling infix expression: ' + input_re)
        self.re_store = input_re
        postfix_re = self.__in2post(input_re)
        self.__print('postfix expression generated: ' + postfix_re)
        self.start_ptr = self.__post2nfa(postfix_re)


    # TODO: Should convert implicit concatentation, e.g. "ab", into explicit
    # concatentation, e.g. "a.b". 
    def __in2post(self, input_str):
        """Converts an infix expression to a postfix expression.

        Why? Postfix notation is useful because parentheses are unneeded since
        the notation does not have the operator-operand ambiguity inherent to
        inﬁx expressions [1].

        We will use "&" for an explicit concatentation operator. Ken Thompson
        originally used "."[2], but we want to use the dot as a wild card. 

        This function's algorithm is from [3].

        Args: An infix expression, e.g. a+b.

        Returns: A postfix expression converted from the input, e.g. ab+.
        """

        post = ''
        stack = []

        for char in input_str:
            if char in self.operators:
                self.__print(char + ' is in the list of operators')

                if len(stack) == 0:
                    self.__print('\t stack empty, placing onto stack')
                    stack.append(char)
                    self.__print('\t stack: ' + str(stack))

                # If `char` has a higher precedence than the top of the stack:
                elif self.__prec(char) > self.__prec(stack[-1]):
                    # Place the new operator on the stack so that it will come
                    # first after the stack is popped. For example, if the
                    # input is A+B*C, and we are parsing the "*", we should see
                    # "+" on the stack and then place "*" on top. When we pop
                    # the stack at end of this function, we'll reverse those
                    # two to produce "ABC*+".
                    self.__print('\t' + char + ' has higher precedence than ' + stack[-1] + '; ' + char + ' placed onto stack')
                    stack.append(char)
                    self.__print('\t stack: ' + str(stack))

                # If `char` has a lower precedence:
                else:
                    self.__print('\t' + char + ' has lower precedence than ' + stack[-1])
                    # If we see an open paren, do not pop operators off stack.
                    if char is '(':
                        # Place open paren on stack as a marker
                        self.__print('\topen paren found, placing on stack')
                        stack.append(char)
                    elif char is ')':
                        # TODO: What if there is no open paren?
                        self.__print('\tclose paren found, pop stack until find open paren')
                        while stack and stack[-1] is not self.metachars['(']:
                            post += stack.pop()
                        # Remove open paren
                        stack.pop()
                    else:
                        while stack and self.__prec(char) <= self.__prec(stack[-1]):
                            self.__print('\t' + char + ' has lower or equal precedence than ' + stack[-1] + ', pop top of stack')
                            post += stack.pop()
                            self.__print('\t\tstack: ' + str(stack))
                            self.__print('\t\tpostfix: ' + post)
                        stack.append(char)
            else:
                self.__print(char + ' is a literal')
                #if len(stack) >= 1 and stack[-1] is '&':
                #    self.__print('\t previous operator was explicit concatenation... adding to string')
                #    post += stack.pop() + char
                #    self.__print('\t ' + post)
                #    # This new character needs its own explicit concatenation.
                #    stack.append('&')
                
                # Handle conversion of implicit to explicit concatenation.
                #else:
                self.__print('\texplicit concatenation')
                if post != '' and post[-1] not in self.operators:
                    self.__print('\tadding & to stack')
                    stack.append('&')
                post += char

        while stack:
            post += stack.pop()
        
        return post


    def __post2nfa(self, post):
        """Converts a postfix expression to an NFA.

        Args: A postfix expression, e.g. ab+ rather than a+b.

        Returns: A pointer to the NFA start state.
        """
        stack = []
        for char in post:
            if char is '+':
                # Remove the NFA fragment currently on the stack. This is the
                # state that we want to repeat. 
                f = stack.pop()
  
                # Create a new NFA state in which the first out state is the
                # state we want to repeat. This creates the loopback.
                s = State(Metachar.split, f.start)

                # Patch the dangling out states of the previous fragment to the
                # newly created state. This completes the loop.
                f.patch(s)
                
                # Add the new fragment onto the stack.
                stack.append( Frag(f.start, [s.out_ptr2]) )

            # Concatentation. This is the important step, because it reduces
            # the number of NFA fragments on the stack.
            elif char is '.':
                f2 = stack.pop()
                f1 = stack.pop()
                f1.patch(f2.start)
                stack.append( Frag(f1.start, f2.dangling_ptr_list) )

            # Character literals
            else:
                s = State(char, True)
                stack.append( Frag(s, [s.out_ptr1]) )

        # In [2] this line of code is a `pop`, but that just shifts the stack
        # pointer. I don't think we actually want to remove this NFA fragment
        # from the stack. 
        nfa = stack[-1]
        nfa.patch( State(Metachar.match) )
        return Ptr(nfa.start)

    
    def __step(self, curr_list_ptr, char, next_list_ptr):
        self.list_id += 1
        clist = curr_list_ptr.get()
        for ptr in clist:
            state = ptr.get()
            if state.trans == char:
                self.__add_state(next_list_ptr, state.out_ptr1)


    def __add_state(self, next_list_ptr, state_ptr):
        state = state_ptr.get()
        if state == None or state.id == self.list_id:
            return
        state.id = self.list_id
        if (state.trans == Metachar.split):
            self.__add_state(next_list_ptr, state.out_ptr1)
            self.__add_state(next_list_ptr, state.out_ptr2)
            return
        next_list_ptr.get().append(state_ptr)

    
    def __is_match(self, states_ptr):
        states = states_ptr.get()
        for s_p in states:
            if s_p.get().trans == Metachar.match:
                return True
        return False


    def __prec(self, char):
        """Calculates operator precedence. See [4].
        """
        return self.operators[char]


    def __print(self, msg):
        if (self.debug):
            print(msg)


if __name__ == '__main__':
    # Default to True for now.
    #if len(sys.argv) == 4:
    #    use_debug = (sys.argv[3] == 'True')
    #else:
    #    use_debug = False

    pyre = Pyre(sys.argv[1], True)
    pyre.match(sys.argv[2])
