# -*- coding: utf-8 -*-

#    Copyright (C) 2013 Rackspace Hosting Inc. All Rights Reserved.
#    Copyright (C) 2013 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc
import logging

import six

from taskflow import atom
from taskflow import exceptions as exc
from taskflow.utils import misc

LOG = logging.getLogger(__name__)

# Decision results.
REVERT = "REVERT"
REVERT_ALL = "REVERT_ALL"
RETRY = "RETRY"


@six.add_metaclass(abc.ABCMeta)
class Decider(object):
    """A class/mixin object that can decide how to resolve execution failures.

    A decider may be executed multiple times on subflow or other atom
    failure and it is expected to make a decision about what should be done
    to resolve the failure (retry, revert to the previous retry, revert
    the whole flow, etc.).
    """

    @abc.abstractmethod
    def on_failure(self, history, *args, **kwargs):
        """On failure makes a decision about the future.

        This method will typically use information about prior failures (if
        this historical failure information is not available or was not
        persisted this history will be empty).

        Returns retry action constant:

        * ``RETRY`` when subflow must be reverted and restarted again (maybe
          with new parameters).
        * ``REVERT`` when this subflow must be completely reverted and parent
          subflow should make a decision about the flow execution.
        * ``REVERT_ALL`` in a case when the whole flow must be reverted and
          marked as ``FAILURE``.
        """


@six.add_metaclass(abc.ABCMeta)
class Retry(atom.Atom, Decider):
    """A class that can decide how to resolve execution failures.

    This abstract base class is used to inherit from and provide different
    strategies that will be activated upon execution failures. Since a retry
    object is an atom it may also provide execute and revert methods to alter
    the inputs of connected atoms (depending on the desired strategy to be
    used this can be quite useful).
    """

    default_provides = None

    def __init__(self, name=None, provides=None, requires=None,
                 auto_extract=True, rebind=None):
        if provides is None:
            provides = self.default_provides
        super(Retry, self).__init__(name, provides)
        self._build_arg_mapping(self.execute, requires, rebind, auto_extract,
                                ignore_list=['history'])

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @abc.abstractmethod
    def execute(self, history, *args, **kwargs):
        """Executes the given retry atom.

        This execution activates a given retry which will typically produce
        data required to start or restart a connected component using
        previously provided values and a history of prior failures from
        previous runs. The historical data can be analyzed to alter the
        resolution strategy that this retry controller will use.

        For example, a retry can provide the same values multiple times (after
        each run), the latest value or some other variation. Old values will be
        saved to the history of the retry atom automatically, that is a list of
        tuples (result, failures) are persisted where failures is a dictionary
        of failures indexed by task names and the result is the execution
        result returned by this retry controller during that failure resolution
        attempt.
        """

    def revert(self, history, *args, **kwargs):
        """Reverts this retry using the given context.

        On revert call all results that had been provided by previous tries
        and all errors caused during reversion are provided. This method
        will be called *only* if a subflow must be reverted without the
        retry (that is to say that the controller has ran out of resolution
        options and has either given up resolution or has failed to handle
        a execution failure).
        """


class AlwaysRevert(Retry):
    """Retry that always reverts subflow."""

    def on_failure(self, *args, **kwargs):
        return REVERT

    def execute(self, *args, **kwargs):
        pass


class AlwaysRevertAll(Retry):
    """Retry that always reverts a whole flow."""

    def on_failure(self, **kwargs):
        return REVERT_ALL

    def execute(self, **kwargs):
        pass


class Times(Retry):
    """Retries subflow given number of times. Returns attempt number."""

    def __init__(self, attempts=1, name=None, provides=None, requires=None,
                 auto_extract=True, rebind=None):
        super(Times, self).__init__(name, provides, requires,
                                    auto_extract, rebind)
        self._attempts = attempts

    def on_failure(self, history, *args, **kwargs):
        if len(history) < self._attempts:
            return RETRY
        return REVERT

    def execute(self, history, *args, **kwargs):
        return len(history) + 1


class ForEachBase(Retry):
    """Base class for retries that iterate over a given collection."""

    def _get_next_value(self, values, history):
        # Fetches the next resolution result to try, removes overlapping
        # entries with what has already been tried and then returns the first
        # resolution strategy remaining.
        items = (item for item, _failures in history)
        remaining = misc.sequence_minus(values, items)
        if not remaining:
            raise exc.NotFound("No elements left in collection of iterable "
                               "retry controller %s" % self.name)
        return remaining[0]

    def _on_failure(self, values, history):
        try:
            self._get_next_value(values, history)
        except exc.NotFound:
            return REVERT
        else:
            return RETRY


class ForEach(ForEachBase):
    """Applies a statically provided collection of strategies.

    Accepts a collection of decision strategies on construction and returns the
    next element of the collection on each try.
    """

    def __init__(self, values, name=None, provides=None, requires=None,
                 auto_extract=True, rebind=None):
        super(ForEach, self).__init__(name, provides, requires,
                                      auto_extract, rebind)
        self._values = values

    def on_failure(self, history, *args, **kwargs):
        return self._on_failure(self._values, history)

    def execute(self, history, *args, **kwargs):
        # NOTE(harlowja): This allows any connected components to know the
        # current resolution strategy being attempted.
        return self._get_next_value(self._values, history)


class ParameterizedForEach(ForEachBase):
    """Applies a dynamically provided collection of strategies.

    Accepts a collection of decision strategies from a predecessor (or from
    storage) as a parameter and returns the next element of that collection on
    each try.
    """

    def on_failure(self, values, history, *args, **kwargs):
        return self._on_failure(values, history)

    def execute(self, values, history, *args, **kwargs):
        return self._get_next_value(values, history)
