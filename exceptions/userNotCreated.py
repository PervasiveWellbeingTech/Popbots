#   Copyright 2020 Stanford University
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
class UserNotCreated(Exception):
    def __init__(self):
        self.intents = intents # intents must be of type list
        super(BadKeywordInputError,self).__init__(intents)

    def __str__(self):
        return "[ERROR] User should have responded with: "+ ",".join(str(x) for x in self.intents)
        #repr(self.message)
