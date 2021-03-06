from scipy.constants import speed_of_light as c  # [m/s]
from scipy.constants import pi as pi
import numpy as np
import itertools
import threading


def lambda_cal(frequency):

    """
    Calculate the wave length of electromagnetic radiation given its frequency.

    :param frequency: Frequency of electromagnetic radiation [MHz]
    :return wavelength: wave length of electromagnetic radiation [m]
    """

    return c * 1e-6 / frequency


def R_cal(sensor_groups, xycoords):
    """
    :param sensor_groups: how many sensor groups are there in the radar configuration. Do not count on the one located \
    at the origin
    :param xycoords: coordinates of the subgroups centers in wave lengths
    :return R: subgroup phase center
    """

    R = np.zeros((3, sensor_groups))
    R[0, :] = xycoords[:sensor_groups, 0]
    R[1, :] = xycoords[:sensor_groups, 1]
    R[2, :] = np.multiply(0, xycoords[:sensor_groups, 0])

    return R


def linCoeff_cal(R):

    """
    Calculate linear coefficients given R.

    :param R: matrix of subgroup phase centers
    """

    return np.sum(R ** 2, axis=0) / np.linalg.norm(R, axis=0)


def p0_jk(j, k, R, n0, K):

    """
    Displacement point

    :param j:
    :param k:
    :param R:
    :param n0:
    :param K:
    """

    return (n0[j] + 1 - k) / K[j] / np.linalg.norm(R[:, j], axis=0) * R[:, j]


def nvec_j(j, R):

    """
    Normalized vector normal to plane j. Each plane is given as a column in R.

    :param j: index
    :param R: subgroup phase center
    """

    return R[:, j] / np.linalg.norm(R[:, j], axis=0)


def mooore_penrose_solution_ptr(W, Wpinv, b_set, intersection_line_set, pinv_norm_set, ind_range):

    """
    Calculate the difference tha produces the use of the Moore-Penrose solution matrix to the algebraic equation in \
    paper.

    :param W: W matrix
    :param Wpinv: Pseudo-inverser of W matrix
    :param b_set: set of b vctors
    :param intersection_line_set: matrix of intersection lines
    :param pinv_norm_set: matrix of pinv_norm vectors
    :param ind_range: index
    """

    for ind in ind_range:
        b = b_set[:, ind].view()

        Moore_Penrose_solution_check = np.linalg.multi_dot([W, Wpinv, b]) - b
        pinv_norm_set[ind] = np.linalg.norm(Moore_Penrose_solution_check)
        intersection_line_set[:, ind] = np.dot(Wpinv, b)


def mooore_penrose_solution_par(W, b_set, pnum, niter, intersection_line_set, pinv_norm_set):

    """
    Calculate the Moore-Penrose solution for each case making use of parallel threading to parallelize task
    and joining results. Calls the function moore_penrose_solution_ptr

    :param W: Matrix representation of all the normal vector of the planes going through the intersection.
    :param b_set: Set ob b vectors for which the solution is going to be computed.
    :param pnum: Number of cores for parallelizing
    :param niter: number of permutations.
    :param intersection_line_set: initial array with zeros where the intersection lines will be allocated.
    :param pinv_norm_set: error in the MP solution approximation

    """

    Wpinv = np.linalg.pinv(W)

    threads = []

    job_id = 0
    if niter % pnum == 0:
        subset = int(niter/pnum)
    else:
        subset = niter//pnum + 1

    while job_id*subset < niter:
        for i in range(pnum):
            if (job_id+1)*subset > niter:
                job_range = range(job_id*subset, niter)
            else:
                job_range = range(job_id*subset, (job_id+1)*subset)
            
            t = threading.Thread(target=mooore_penrose_solution_ptr,
                                 args=[W,
                                       Wpinv,
                                       b_set,
                                       intersection_line_set,
                                       pinv_norm_set,
                                       job_range])

            threads.append(t)
            t.start()
            job_id+=1

    for t in threads:
        t.join()

def mooore_penrose_solution (W, b):

    """
    Calculate the difference that produces the use of the Moore-Penrose solution matrix to the algebraic equation

    :param W: W matrix as described in paper
    :param b: b vector as described in paper
    :return intersection_line: matrix of intersection lines
    :return pinv_norm: difference after solution check

    """

    Moore_Penrose_solution_check = np.linalg.multi_dot([W, np.linalg.pinv(W), b]) - b
    intersection_line = np.dot(np.linalg.pinv(W), b)[:, 0]
    pinv_norm= np.linalg.norm(Moore_Penrose_solution_check)

    return intersection_line, pinv_norm


def intersections_cal(pinv_norm, PERMS_J, intersection_line, R, **kwargs):

    """
    Given that the Moore-Penrose solution gives a solution for any case. It is necessary to choose the ones whose \
    error is below a given tolerance value.

    :param pinv_norm: distance from real b_vector and the one obtained by the moore_penrose solution
    :param PERMS_J: Valid combinations
    :param intersection_line: matrix of intersection lines
    :param R: subgroup phase center
    :param kwargs: if 'norm' an extra condition will be applied and is that if pinv_norm is greater than zero, it \
    will disregarded.
    :return intersections: dictionary with the so far valid intersection combinations.

    """
    mp_tol = 0.1
    intersections = dict()

    if 'norm' in kwargs:
        intersections['indexes'] = np.where(
            (pinv_norm < mp_tol) & (kwargs['norm'] <= 2) & (kwargs['norm'] != 0))
    else:
        intersections['indexes'] = np.where(pinv_norm < mp_tol)

    intersections['number'] = len(intersections['indexes'][0])
    intersections['permutations'] = np.array(PERMS_J)[intersections['indexes'][0]]

    integers = (
        np.repeat(np.transpose(R)[:, :, np.newaxis], repeats=intersections['number'], axis=2)[:, :, None] * np.reshape(
            intersection_line[:, intersections['indexes'][0]], (3, 1, intersections['number']))).sum(axis=1)

    intersections['integers'] = np.reshape(integers, (np.shape(integers)[0], intersections['number']))

    return intersections


def permutations_create(permutations_base, intersections_ind, k_length, permutation_index):

    """
    Create all possible permutations by combining current permutation combinations with valid indexes and new


    :param permutations_base: set of combinations created so far
    :param intersections_ind: indexes of valid combinations
    :param k_length: set of elements to create new permutations, k
    :param permutation_index: index of current permutation. Chooses k_j

    """

    iterables = [np.array(permutations_base)[intersections_ind[0], :], range(1, int(k_length[permutation_index]) + 1)]

    return list(itertools.product(*iterables))


def k0_cal(el0, az0):

    """
    Calculation of wave vector defined defined in paper.

    :param el0: elevation angle [º]
    :param az0: azimuth angle [º]
    """

    return [np.sin(np.radians(az0)) * np.cos(np.radians(el0)), np.cos(np.radians(az0)) * np.cos(
        np.radians(el0)), np.sin(np.radians(el0))]


def slines_intersections(k0, intersections_ind, intersection_line, cutoff_ph_ang):

    """
    Find all s-lines that intersect with the cap by range check.


    :param k0: wave vector
    :param intersections_ind: indexes of valid combinations
    :param intersection_line: intersection lines matrix
    :param cutoff_ph_ang: cut-off angle
    """

    cap = np.repeat([[k0[0]], [k0[1]]], repeats=len(intersections_ind), axis=1) -\
          intersection_line[0:2, intersections_ind]
    cap = np.sqrt(np.sum(cap ** 2, axis=0))
    cap = np.where(cap <= np.sin(cutoff_ph_ang))

    return cap


def explicit(intersection_line, intersections_ind, cap_intersections_of_slines, xy, k0):

    """
    Calculation of ambiguities

    :param intersection_line: matrix of intersection lines as columns
    :param intersections_ind: valid intersection indexes
    :param cap_intersections_of_slines: cap?
    :param xy: xy coordinates of radar subgroups
    :param k0: signal wave vector
    :returns:
        * **ambiguity_distances_explicit** - ambiguity distances
        * **ambiguity_normal_explicit** -
        * **k_finds** -
    """

    s_sel = intersection_line[:, intersections_ind[cap_intersections_of_slines]]

    aux1 = np.repeat([[k0[0]], [k0[1]]], repeats=np.shape(s_sel)[1], axis=1) - s_sel[0:2, :]
    aux2 = np.sqrt(1 - aux1[0, :] ** 2 - aux1[1, :] ** 2)

    k_finds = np.vstack((aux1, aux2))

    subgroup_signal_k0 = np.exp(-1j * 2 * pi * (xy[:, 0] * k0[0] + xy[:, 1] * k0[1]))
    subgroup_signal = np.exp(-1j * 2 * pi * (
            np.transpose(np.repeat([xy[:, 0]], repeats=np.shape(k_finds)[1], axis=0)) * np.repeat(
        [k_finds[0, :]], repeats=np.shape(xy)[0], axis=0) + np.transpose(np.repeat([xy[:, 1]], repeats=np.shape(
        k_finds)[1], axis=0)) * np.repeat([k_finds[1, :]], repeats=np.shape(xy)[0], axis=0)))

    ambiguity_distances_explicit = np.linalg.norm(np.transpose(np.repeat([subgroup_signal_k0], repeats=np.shape(
        k_finds)[1], axis=0)) - subgroup_signal, axis=0)

    ambiguity_normal_explicit = (np.transpose(np.repeat([subgroup_signal_k0], repeats=np.shape(
        k_finds)[1], axis=0)) - subgroup_signal) / np.repeat([ambiguity_distances_explicit], repeats=np.shape(
        subgroup_signal)[0], axis=0)

    return ambiguity_distances_explicit, ambiguity_normal_explicit, k_finds
