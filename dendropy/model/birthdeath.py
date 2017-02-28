#! /usr/bin/env python

##############################################################################
##  DendroPy Phylogenetic Computing Library.
##
##  Copyright 2010-2015 Jeet Sukumaran and Mark T. Holder.
##  All rights reserved.
##
##  See "LICENSE.rst" for terms and conditions of usage.
##
##  If you use this work or any portion thereof in published work,
##  please cite it as:
##
##     Sukumaran, J. and M. T. Holder. 2010. DendroPy: a Python library
##     for phylogenetic computing. Bioinformatics 26: 1569-1571.
##
##############################################################################

"""
Models, modeling and model-fitting of birth-death processes.
"""

import sys
import math
import collections
import itertools
from dendropy.calculate import probability
from dendropy.utility import GLOBAL_RNG
from dendropy.utility.error import TreeSimTotalExtinctionException
from dendropy.utility import constants

import dendropy

def birth_death_tree(birth_rate, death_rate, birth_rate_sd=0.0, death_rate_sd=0.0, **kwargs):
    """
    Returns a birth-death tree with birth rate specified by ``birth_rate``, and
    death rate specified by ``death_rate``, with edge lengths in continuous (real)
    units.

    Tree growth is controlled by one or more of the following arguments, of which
    at least one must be specified:

        - If ``num_extant_tips`` is given as a keyword argument, tree is grown until the
          number of EXTANT tips equals this number.
        - If ``num_extinct_tips`` is given as a keyword argument, tree is grown until the
          number of EXTINCT tips equals this number.
        - If ``num_total_tips`` is given as a keyword argument, tree is grown until the
          number of EXTANT plus EXTINCT tips equals this number.
        - If 'max_time' is given as a keyword argument, tree is grown for
          a maximum of ``max_time``.
        - If ``gsa_ntax`` is given then the tree will be simulated up to this number of
          EXTANT tips (or 0 tips), then a tree will be randomly selected from the
          intervals which corresond to times at which the tree had exactly ``num_extant_tips``
          leaves. This allows for simulations according to the "General
          Sampling Approach" of Hartmann et al. (2010). If this option is
          specified, then ``num_extant_tips`` MUST be specified and
          ``num_extinct_tips`` and ``num_total_tips`` CANNOT be specified.

    If more than one of the above is given, then tree growth will terminate when
    *any* of the termination conditions (i.e., number of tips == ``ntax`` or
    maximum time = ``max_time``) are met.

    Parameters
    ----------

    birth_rate : float
        The birth rate.
    death_rate : float
        The death rate.
    birth_rate_sd : float
        The standard deviation of the normally-distributed mutation added to
        the birth rate as it is inherited by daughter nodes; if 0, birth rate
        does not evolve on the tree.
    death_rate_sd : float
        The standard deviation of the normally-distributed mutation added to
        the death rate as it is inherited by daughter nodes; if 0, death rate
        does not evolve on the tree.

    Keyword Arguments
    -----------------

    ntax: integer
        If specified, then tree will grown until the number of EXTANT tips equals this number.
    tree : Tree
        If given, then this tree will be used; otherwise a new one will be created.
    is_assign_extant_taxa : bool [default: True]
        If False, then taxa will not be assigned to extant tips. If True
        (default), then taxa will be assigned to extant tips. Taxa will be
        assigned from the specified ``taxon_namespace`` or
        ``tree.taxon_namespace``. If the number of taxa required exceeds the
        number of taxa existing in the taxon namespace, new |Taxon| objects
        will be created as needed and added to the taxon namespace.
    is_assign_extinct_taxa : bool [default: True]
        If False, then taxa will not be assigned to extant tips. If True
        (default), then taxa will be assigned to extant tips. Taxa will be
        assigned from the specified ``taxon_namespace`` or
        ``tree.taxon_namespace``. If the number of taxa required exceeds the
        number of taxa existing in the taxon namespace, new |Taxon| objects
        will be created as needed and added to the taxon namespace. Note that
        this option only makes sense if extinct tips are retained (specified via
        'is_retain_extinct_tips' option), and will otherwise be ignored.
    is_add_extinct_attr: bool [default: True]
        If True (default), add an boolean attribute indicating whether or not a
        node is an extinct tip or not. False will skip this. Name of attribute
        is set by 'extinct_attr_name' argument, defaulting to 'is_extinct'.
        Note that this option only makes sense if extinct tips are retained
        (specified via 'is_retain_extinct_tips' option), and will otherwise be
        ignored.
    extinct_attr_name: str [default: 'is_extinct']
        Name of attribute to add to nodes indicating whether or not tip is extinct.
        Note that this option only makes sense if extinct tips are retained
        (specified via 'is_retain_extinct_tips' option), and will otherwise be
        ignored.
    is_retain_extinct_tips : bool [default: False]
        If True, extinct tips will be retained on tree. Defaults to False:
        extinct lineages removed from tree.
    repeat_until_success: bool [default: True]
        Under some conditions, it is possible for all lineages on a tree to go
        extinct. In this case, if this argument is given as |True| (the
        default), then a new branching process is initiated. If |False|
        (default), then a TreeSimTotalExtinctionException is raised.
    rng: random.Random() or equivalent instance
        A Random() object or equivalent can be passed using the ``rng`` keyword;
        otherwise GLOBAL_RNG is used.

    References
    ----------

    Hartmann, Wong, and Stadler "Sampling Trees from Evolutionary Models" Systematic Biology. 2010. 59(4). 465-476

    """
    if "assign_taxa" in kwargs:
        raise ValueError("'assign_taxa' is no longer supported in this function; please use 'is_assign_extant_taxa' and/or 'is_assign_extinct_taxa' instead")
    if "ntax" in kwargs:
        raise ValueError("'ntax' is no longer supported as an argument to this function. One or more of the following must be specified: 'num_extant_tips', 'num_extinct_tips', or 'max_time' instead")
    if (
        ("num_extant_tips" not in kwargs)
        and ("num_extinct_tips" not in kwargs)
        and ("num_total_tips" not in kwargs)
        and ("max_time" not in kwargs) ):
            raise ValueError("One or more of the following must be specified: 'num_extant_tips', 'num_extinct_tips', or 'max_time'")
    target_num_extant_tips = kwargs.pop("num_extant_tips", None)
    target_num_extinct_tips = kwargs.pop("num_extinct_tips", None)
    target_num_total_tips = kwargs.pop("num_total_tips", None)
    max_time = kwargs.pop('max_time', None)
    gsa_ntax = kwargs.pop('gsa_ntax', None)
    is_add_extinct_attr = kwargs.pop('is_add_extinct_attr', True)
    extinct_attr_name = kwargs.pop('extinct_attr_name', 'is_extinct')
    is_retain_extinct_tips = kwargs.pop('is_retain_extinct_tips', False)
    is_assign_extant_taxa = kwargs.pop('is_assign_extant_taxa', True)
    is_assign_extinct_taxa = kwargs.pop('is_assign_extinct_taxa', True)
    repeat_until_success = kwargs.pop('repeat_until_success', True)

    tree = kwargs.get("tree", None)
    taxon_namespace = kwargs.get("taxon_namespace", None)

    rng = kwargs.pop('rng', GLOBAL_RNG)

    # if "tree" in kwargs:
    #     if "taxon_namespace" in kwargs and kwargs['taxon_namespace'] is not tree.taxon_namespace:
    #         raise ValueError("Cannot specify both ``tree`` and ``taxon_namespace``")
    #     taxon_namespace = kwargs.pop("taxon_namespace", None)
    # elif "taxon_namespace" in kwargs:
    #     taxon_namespace = kwargs.pop("taxon_namespace", None)
    # else:
    #     taxon_namespace = dendropy.TaxonNamespace()
    ignore_unrecognized_keyword_arguments = kwargs.pop('ignore_unrecognized_keyword_arguments', False)
    if kwargs and not ignore_unrecognized_keyword_arguments:
        raise ValueError("Unrecognized keyword arguments: ".format(kwargs))

    terminate_at_full_tree = False

    if gsa_ntax is None:
        terminate_at_full_tree = True
        # gsa_ntax = 1 + target_num_taxa
    elif target_num_extant_tips is None:
        raise ValueError("If 'gsa_ntax' is specified, 'num_extant_tips' must be specified")
    elif target_num_extinct_tips is not None:
        raise ValueError("If 'gsa_ntax' is specified, 'num_extinct_tups' cannot be specified")
    elif target_num_total_tips is not None:
        raise ValueError("If 'gsa_ntax' is specified, 'num_total_tips' cannot be specified")
    elif gsa_ntax < target_num_extant_tips:
        raise ValueError("'gsa_ntax' must be greater than 'num_extant_tips'")

    # initialize tree
    if tree is not None:
        if taxon_namespace is not None:
            assert tree.taxon_namespace is taxon_namespace
        else:
            taxon_namespace = tree.taxon_namespace
        extant_tips = set()
        extinct_tips = set()
        for nd in tree:
            if not nd._child_nodes:
                if getattr(nd, extinct_attr_name, False):
                    extant_tips.add(nd)
                    if is_add_extinct_attr:
                        setattr(nd, extinct_attr_name, False)
                else:
                    extinct_tips.append(nd)
                    if is_add_extinct_attr:
                        setattr(nd, extinct_attr_name, True)
            elif is_add_extinct_attr:
                setattr(nd, extinct_attr_name, None)
    else:
        if taxon_namespace is None:
            taxon_namespace = dendropy.TaxonNamespace()
        tree = dendropy.Tree(taxon_namespace=taxon_namespace)
        tree.is_rooted = True
        tree.seed_node.edge.length = 0.0
        tree.seed_node.birth_rate = birth_rate
        tree.seed_node.death_rate = death_rate
        if is_add_extinct_attr:
            setattr(tree.seed_node, extinct_attr_name, False)
        extant_tips = set([tree.seed_node])
        extinct_tips = set()
    initial_extant_tip_set = set(extant_tips)
    initial_extinct_tip_set = set(extinct_tips)

    total_time = 0

    # for the GSA simulations targetted_time_slices is a list of tuple
    #   the first element in the tuple is the duration of the amount
    #   that the simulation spent at the (targetted) number of taxa
    #   and a list of edge information. The list of edge information includes
    #   a list of terminal edges in the tree and the length for that edge
    #   that marks the beginning of the time slice that corresponds to the
    #   targetted number of taxa.
    targetted_time_slices = []

    while True:
        if gsa_ntax is None:
            if target_num_extant_tips is not None and len(extant_tips) >= target_num_extant_tips:
                break
            if target_num_extinct_tips is not None and len(extinct_tips) >= target_num_extinct_tips:
                break
            if target_num_total_tips is not None and (len(extant_tips) + len(extinct_tips)) >= target_num_total_tips:
                break
            if max_time is not None and total_time >= max_time:
                break
        elif len(extant_tips) >= gsa_ntax:
            break

        # get vector of birth/death probabilities, and
        # associate with nodes/events
        event_rates = []
        event_nodes = []
        for nd in extant_tips:
            if not hasattr(nd, 'birth_rate'):
                nd.birth_rate = birth_rate
            if not hasattr(nd, 'death_rate'):
                nd.death_rate = death_rate
            event_rates.append(nd.birth_rate)
            event_nodes.append((nd, True)) # birth event = True
            event_rates.append(nd.death_rate)
            event_nodes.append((nd, False)) # birth event = False; i.e. death

        # get total probability of any birth/death
        rate_of_any_event = sum(event_rates)

        # waiting time based on above probability
        waiting_time = rng.expovariate(rate_of_any_event)

        if ( (gsa_ntax is not None)
                and (len(extant_tips) == target_num_extant_tips)
                ):
            edge_and_start_length = []
            for nd in extant_tips:
                e = nd.edge
                edge_and_start_length.append((e, e.length))
            targetted_time_slices.append((waiting_time, edge_and_start_length))
            if terminate_at_full_tree:
                break

        # add waiting time to nodes
        for nd in extant_tips:
            try:
                nd.edge.length += waiting_time
            except TypeError:
                nd.edge.length = waiting_time
        total_time += waiting_time

        # if event occurs within time constraints
        if max_time is None or total_time <= max_time:
            # normalize probability
            for i in range(len(event_rates)):
                event_rates[i] = event_rates[i]/rate_of_any_event
            # select node/event and process
            nd, birth_event = probability.weighted_choice(event_nodes, event_rates, rng=rng)
            extant_tips.remove(nd)
            if birth_event:
                if is_add_extinct_attr:
                    setattr(nd, extinct_attr_name, None)
                c1 = nd.new_child()
                c2 = nd.new_child()
                c1.edge.length = 0
                c2.edge.length = 0
                c1.birth_rate = nd.birth_rate + rng.gauss(0, birth_rate_sd)
                c1.death_rate = nd.death_rate + rng.gauss(0, death_rate_sd)
                c2.birth_rate = nd.birth_rate + rng.gauss(0, birth_rate_sd)
                c2.death_rate = nd.death_rate + rng.gauss(0, death_rate_sd)
                extant_tips.add(c1)
                extant_tips.add(c2)
            else:
                if len(extant_tips) > 0:
                    extinct_tips.add(nd)
                    if is_add_extinct_attr:
                        setattr(nd, extinct_attr_name, None)
                else:
                    # total extinction
                    if (gsa_ntax is not None):
                        if (len(targetted_time_slices) > 0):
                            break
                    if not repeat_until_success:
                        raise TreeSimTotalExtinctionException()
                    # We are going to basically restart the simulation because
                    # the tree has gone extinct (without reaching the specified
                    # ntax)
                    extant_tips = set(initial_extant_tip_set)
                    extinct_tips = set(initial_extinct_tip_set)
                    for nd in extant_tips:
                        if is_add_extinct_attr:
                            setattr(nd, extinct_attr_name, False)
                        nd.clear_child_nodes()
                    total_time = 0

    if gsa_ntax is not None:
        total_duration_at_target_n_tax = 0.0
        for i in targetted_time_slices:
            total_duration_at_target_n_tax += i[0]
        r = rng.random()*total_duration_at_target_n_tax
        selected_slice = None
        for n, i in enumerate(targetted_time_slices):
            r -= i[0]
            if r < 0.0:
                selected_slice = i
        assert(selected_slice is not None)
        edges_at_slice = selected_slice[1]
        last_waiting_time = selected_slice[0]

        for e, prev_length in edges_at_slice:
            daughter_nd = e.head_node
            for nd in daughter_nd.child_nodes():
                nd._parent_node = None
                extinct_tips.discard(nd)
                extant_tips.discard(nd)
                for desc in nd.preorder_iter():
                    extinct_tips.discard(desc)
                    extant_tips.discard(desc)
            daughter_nd.clear_child_nodes()
            extinct_tips.discard(daughter_nd)
            extant_tips.add(daughter_nd)
            if is_add_extinct_attr:
                setattr(daughter_nd, extinct_attr_name, False)
            e.length = prev_length + last_waiting_time

    if not is_retain_extinct_tips:
        for nd in extinct_tips:
            assert not nd._child_nodes
            while (nd.parent_node is not None) and (len(nd.parent_node._child_nodes) == 1):
                nd = nd.parent_node
            if nd.parent_node:
                tree.prune_subtree(nd, suppress_unifurcations=False)
    tree.suppress_unifurcations()

    if is_assign_extant_taxa or is_assign_extinct_taxa:
        taxon_pool = [t for t in taxon_namespace]

        ### ONLY works if in GSA sub-section we remove ALL extant and
        ### extinct nodes beyond time slice: expensive
        node_pool_labels = ("T", "X")
        for node_pool_idx, node_pool in enumerate((extant_tips, extinct_tips)):
            for node_idx, nd in enumerate(node_pool):
                if taxon_pool:
                    taxon = taxon_pool.pop()
                else:
                    taxon = taxon_namespace.require_taxon("{}{}".format(node_pool_labels[node_pool_idx], node_idx+1))
                nd.taxon = taxon

    return tree


def discrete_birth_death_tree(birth_rate, death_rate, birth_rate_sd=0.0, death_rate_sd=0.0, **kwargs):
    """
    Returns a birth-death tree with birth rate specified by ``birth_rate``, and
    death rate specified by ``death_rate``, with edge lengths in discrete (integer)
    units.

    ``birth_rate_sd`` is the standard deviation of the normally-distributed mutation
    added to the birth rate as it is inherited by daughter nodes; if 0, birth
    rate does not evolve on the tree.

    ``death_rate_sd`` is the standard deviation of the normally-distributed mutation
    added to the death rate as it is inherited by daughter nodes; if 0, death
    rate does not evolve on the tree.

    Tree growth is controlled by one or more of the following arguments, of which
    at least one must be specified:

        - If ``ntax`` is given as a keyword argument, tree is grown until the number of
          tips == ntax.
        - If ``taxon_namespace`` is given as a keyword argument, tree is grown until the
          number of tips == len(taxon_namespace), and the taxa are assigned randomly to the
          tips.
        - If 'max_time' is given as a keyword argument, tree is grown for ``max_time``
          number of generations.

    If more than one of the above is given, then tree growth will terminate when
    *any* of the termination conditions (i.e., number of tips == ``ntax``, or number
    of tips == len(taxon_namespace) or number of generations = ``max_time``) are met.

    Also accepts a Tree object (with valid branch lengths) as an argument passed
    using the keyword ``tree``: if given, then this tree will be used; otherwise
    a new one will be created.

    If ``assign_taxa`` is False, then taxa will *not* be assigned to the tips;
    otherwise (default), taxa will be assigned. If ``taxon_namespace`` is given
    (``tree.taxon_namespace``, if ``tree`` is given), and the final number of tips on the
    tree after the termination condition is reached is less then the number of
    taxa in ``taxon_namespace`` (as will be the case, for example, when
    ``ntax`` < len(``taxon_namespace``)), then a random subset of taxa in ``taxon_namespace`` will
    be assigned to the tips of tree. If the number of tips is more than the number
    of taxa in the ``taxon_namespace``, new Taxon objects will be created and added
    to the ``taxon_namespace`` if the keyword argument ``create_required_taxa`` is not given as
    False.

    Under some conditions, it is possible for all lineages on a tree to go extinct.
    In this case, if the keyword argument ``repeat_until_success`` is |True|, then a new
    branching process is initiated.
    If |False| (default), then a TreeSimTotalExtinctionException is raised.

    A Random() object or equivalent can be passed using the ``rng`` keyword;
    otherwise GLOBAL_RNG is used.
    """
    if 'ntax' not in kwargs \
        and 'taxon_namespace' not in kwargs \
        and 'max_time' not in kwargs:
            raise ValueError("At least one of the following must be specified: 'ntax', 'taxon_namespace', or 'max_time'")
    target_num_taxa = None
    taxon_namespace = None
    target_num_gens = kwargs.get('max_time', None)
    if 'taxon_namespace' in kwargs:
        taxon_namespace = kwargs.get('taxon_namespace')
        target_num_taxa = kwargs.get('ntax', len(taxon_namespace))
    elif 'ntax' in kwargs:
        target_num_taxa = kwargs['ntax']
    if taxon_namespace is None:
        taxon_namespace = dendropy.TaxonNamespace()
    repeat_until_success = kwargs.get('repeat_until_success', False)
    rng = kwargs.get('rng', GLOBAL_RNG)

    # grow tree
    if "tree" in kwargs:
        tree = kwargs['tree']
        if "taxon_namespace" in kwargs and kwargs['taxon_namespace'] is not tree.taxon_namespace:
            raise ValueError("Cannot specify both ``tree`` and ``taxon_namespace``")
    else:
        tree = dendropy.Tree(taxon_namespace=taxon_namespace)
        tree.is_rooted = True
        tree.seed_node.edge.length = 0
        tree.seed_node.birth_rate = birth_rate
        tree.seed_node.death_rate = death_rate
    leaf_nodes = tree.leaf_nodes()
    num_gens = 0
    while (target_num_taxa is None or len(leaf_nodes) < target_num_taxa) \
            and (target_num_gens is None or num_gens < target_num_gens):
        for nd in leaf_nodes:
            if not hasattr(nd, 'birth_rate'):
                nd.birth_rate = birth_rate
            if not hasattr(nd, 'death_rate'):
                nd.death_rate = death_rate
            try:
                nd.edge.length += 1
            except TypeError:
                nd.edge.length = 1
            u = rng.uniform(0, 1)
            if u < nd.birth_rate:
                c1 = nd.new_child()
                c2 = nd.new_child()
                c1.edge.length = 0
                c2.edge.length = 0
                c1.birth_rate = nd.birth_rate + rng.gauss(0, birth_rate_sd)
                c1.death_rate = nd.death_rate + rng.gauss(0, death_rate_sd)
                c2.birth_rate = nd.birth_rate + rng.gauss(0, birth_rate_sd)
                c2.death_rate = nd.death_rate + rng.gauss(0, death_rate_sd)
            elif u > nd.birth_rate and u < (nd.birth_rate + nd.death_rate):
                if nd is not tree.seed_node:
                    tree.prune_subtree(nd)
                elif not repeat_until_success:
                    # all lineages are extinct: raise exception
                    raise TreeSimTotalExtinctionException()
                else:
                    # all lineages are extinct: repeat
                    num_gens = 0

        num_gens += 1
        leaf_nodes = tree.leaf_nodes()

    # If termination condition specified by ntax or taxon_namespace, then the last
    # split will have a daughter edges of length == 0;
    # so we continue growing the edges until the next birth/death event *or*
    # the max number of generations condition is given and met
    gens_to_add = 0
    while (target_num_gens is None or num_gens < target_num_gens):
        u = rng.uniform(0, 1)
        if u < (birth_rate + death_rate):
            break
        gens_to_add += 1
    for nd in tree.leaf_nodes():
        nd.edge.length += gens_to_add

    if kwargs.get("assign_taxa", True):
        tree.randomly_assign_taxa(create_required_taxa=True, rng=rng)

    # return
    return tree

def uniform_pure_birth_tree(taxon_namespace, birth_rate=1.0, rng=None):
    "Generates a uniform-rate pure-birth process tree. "
    if rng is None:
        rng = GLOBAL_RNG # use the global rng by default
    tree = dendropy.Tree(taxon_namespace=taxon_namespace)
    tree.seed_node.edge.length = 0.0
    leaf_nodes = tree.leaf_nodes()
    while len(leaf_nodes) < len(taxon_namespace):
        waiting_time = rng.expovariate(len(leaf_nodes)/birth_rate)
        for nd in leaf_nodes:
            nd.edge.length += waiting_time
        parent_node = rng.choice(leaf_nodes)
        c1 = parent_node.new_child()
        c2 = parent_node.new_child()
        c1.edge.length = 0.0
        c2.edge.length = 0.0
        leaf_nodes = tree.leaf_nodes()
    leaf_nodes = tree.leaf_nodes()
    waiting_time = rng.expovariate(len(leaf_nodes)/birth_rate)
    for nd in leaf_nodes:
        nd.edge.length += waiting_time
    for idx, leaf in enumerate(leaf_nodes):
        leaf.taxon = taxon_namespace[idx]
    tree.is_rooted = True
    return tree

def fit_pure_birth_model(**kwargs):
    """
    Calculates the maximum-likelihood estimate of the birth rate of a set of
    *internal* node ages under a Yule (pure-birth) model.

    Requires either a |Tree| object or an interable of *internal* node
    ages to be passed in via keyword arguments ``tree`` or ``internal_node_ages``,
    respectively. The former is more convenient when doing one-off
    calculations, while the latter is more efficient if the list of internal
    node ages needs to be used in other places and you already have it
    calculated and want to avoid re-calculating it here.

    Parameters
    ----------
    \*\*kwargs : keyword arguments, mandatory

        Exactly *one* of the following *must* be specified:

            tree : a |Tree| object.
                A |Tree| object. The tree needs to be ultrametric for the
                internal node ages (time from each internal node to the tips)
                to make sense. The precision by which the ultrametricity is
                checked can be specified using the ``ultrametricity_precision`` keyword
                argument (see below). If ``tree`` is given, then
                ``internal_node_ages`` cannot be given, and vice versa. If ``tree``
                is not given, then ``internal_node_ages`` must be given.
            internal_node_ages : iterable (of numerical values)
                Iterable of node ages of the internal nodes of a tree, i.e., the
                list of sum of the edge lengths between each internal node and
                the tips of the tree. If ``internal_node_ages`` is given, then
                ``tree`` cannot be given, and vice versa. If ``internal_node_ages``
                is not given, then ``tree`` must be given.

        While the following is optional, and is only used if internal node ages
        need to be calculated (i.e., 'tree' is passed in).

            ultrametricity_precision : float
                When calculating the node ages, an error will be raised if the tree in
                o ultrametric. This error may be due to floating-point or numerical
                imprecision. You can set the precision of the ultrametricity validation
                by setting the ``ultrametricity_precision`` parameter. E.g., use
                ``ultrametricity_precision=0.01`` for a more relaxed precision,
                down to 2 decimal places. Use ``ultrametricity_precision=False``
                to disable checking of ultrametricity precision.

            ignore_likelihood_calculation_failure: bool (default: False)
                In some cases (typically, abnormal trees, e.g., 1-tip), the
                likelihood estimation will fail. In this case a ValueError will
                be raised. If ``ignore_likelihood_calculation_failure`` is
                |True|, then the function call will still succeed, with the
                likelihood set to -``inf``.

    Returns
    -------
    m : dictionary

    A dictionary with keys being parameter names and values being
    estimates:

        "birth_rate"
            The birth rate.
        "log_likelihood"
            The log-likelihood of the model and given birth rate.

    Examples
    --------

    Given trees such as::

        import dendropy
        from dendropy.model import birthdeath
        trees = dendropy.TreeList.get_from_path(
                "pythonidae.nex", "nexus")

    Birth rates can be estimated by passing in trees directly::

        for idx, tree in enumerate(trees):
            m = birthdeath.fit_pure_birth_model(tree=tree)
            print("Tree {}: birth rate = {} (logL = {})".format(
                idx+1, m["birth_rate"], m["log_likelihood"]))

    Or by pre-calculating and passing in a list of node ages::

        for idx, tree in enumerate(trees):
            m = birthdeath.fit_pure_birth_model(
                    internal_node_ages=tree.internal_node_ages())
            print("Tree {}: birth rate = {} (logL = {})".format(
                idx+1, m["birth_rate"], m["log_likelihood"]))


    Notes
    -----
    Adapted from the laser package for R:

        -   Dan Rabosky and Klaus Schliep (2013). laser: Likelihood Analysis of
            Speciation/Extinction Rates from Phylogenies. R package version
            2.4-1. http://CRAN.R-project.org/package=laser

    See also:

        -   Nee, S.  2001.  Inferring speciation rates from phylogenies.
            Evolution 55:661-668.
        -   Yule, G. U. 1924. A mathematical theory of evolution based on the
            conclusions of Dr.  J. C. Willis. Phil. Trans. R. Soc. Lond. B
            213:21-87.

    """
    tree = kwargs.get("tree", None)
    if tree is not None:
        internal_node_ages = tree.internal_node_ages(ultrametricity_precision=kwargs.get("ultrametricity_precision", 0.0000001))
    else:
        try:
            internal_node_ages = kwargs["internal_node_ages"]
        except KeyError:
            raise TypeError("Need to specify 'tree' or 'internal_node_ages'")
    x = sorted(internal_node_ages, reverse=True)
    st1 = x[0]
    st2 = 0
    nvec = range(2, len(x)+2)
    nv = [i for i in x if (i < st1) and (i >= st2)]
    lo = max(nvec[idx] for idx, i in enumerate(x) if i >= st1)
    up = max(nvec[idx] for idx, i in enumerate(x) if i >= st2)
    if st1 <= x[0]:
        nv.insert(0, st1)
        nv = [i - st2 for i in nv]
    else:
        nv = [i - st2 for i in nv]
    t1 = (up-lo)
    t2 = (lo*nv[0])
    t3 = sum( nv[1:(up-lo+1)] )
    smax = t1/(t2 + t3)

    try:
        s1 = sum(map(math.log, range(lo,up)))
        s2 = (up-lo) * math.log(smax)
        s3 = lo - up
        lh = s1 + s2 + s3
    except ValueError:
        if kwargs.get("ignore_likelihood_calculation_failure", False):
            raise ValueError("Likelihood estimation failure")
        else:
            lh = float("-inf")

    result = {
        "birth_rate" : smax,
        "log_likelihood" : lh,
    }
    return result

def fit_pure_birth_model_to_tree(tree, ultrametricity_precision=constants.DEFAULT_ULTRAMETRICITY_PRECISION):
    """
    Calculates the maximum-likelihood estimate of the birth rate a tree under a
    Yule (pure-birth) model.

    Parameters
    ----------
    tree : |Tree| object
        A tree to be fitted.

    Returns
    -------
    m : dictionary

    A dictionary with keys being parameter names and values being
    estimates:

        -   "birth_rate"
            The birth rate.
        -   "log_likelihood"
            The log-likelihood of the model and given birth rate.

    Examples
    --------

    ::

        import dendropy
        from dendropy.model import birthdeath
        trees = dendropy.TreeList.get_from_path(
                "pythonidae.nex", "nexus")
        for idx, tree in enumerate(trees):
            m = birthdeath.fit_pure_birth_model_to_tree(tree)
            print("Tree {}: birth rate = {} (logL = {})".format(
                idx+1, m["birth_rate"], m["log_likelihood"]))

    """
    return fit_pure_birth_model(tree=tree, ultrametricity_precision=ultrametricity_precision)

