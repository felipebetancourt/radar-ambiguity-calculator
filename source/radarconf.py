import matplotlib.pyplot as plt
from scipy.spatial import ConvexHull
from functions import *
import itertools
from mpl_toolkits.mplot3d import Axes3D
from time import time
import dill

# put latex in figures
from matplotlib import rc

rc('text', usetex=True)
rc('font', family='serif')

t = time()

# Parameters
mp_tol = 1e-1

gain_yagi = 7.24
gain_yagi_base = 10**(gain_yagi/10)

radar = 'JICAMARCA'

if radar == 'JONES':
    lambda0 = lambda0(frequency=31)
    xycoords = np.array([[0, 2], [0, -2.5], [-2, 0], [2.5, 0], [0, 0]])
elif radar == 'JICAMARCA':
    lambda0 = lambda0(frequency=31)
    d = 144
    xycoords = np.array([[-d/lambda0/2, -d-lambda0/2],
                [d/lambda0/2, -d/lambda0/2],
                [d/lambda0/2, d/lambda0/2],
                [-(36+36/2)/lambda0, (36*3+36/2)/lambda0],
                [-(36+36/2)/lambda0, (36*2+36/2)/lambda0],
                [-(36*2+36/2)/lambda0, (36*2+36/2)/lambda0]
                ])

xpos = np.zeros((np.shape(xycoords)[0], 1)) * lambda0
ypos = np.zeros((np.shape(xycoords)[0], 1)) * lambda0
zpos = np.zeros((np.shape(xycoords)[0], 1)) * lambda0


# CODE STARTS HERE

xant = xpos / lambda0
yant = ypos / lambda0

# Subgroup size
Zn = np.shape(zpos)[1]

# Do not count the last group as it is defined as the origin
# Sn : sensor_groups
Sn = np.shape(zpos)[0] - 1

##
r, R, rho = rRrho_cal(sensor_groups=Sn, subgroup_size=Zn, xycoords=xycoords, xpos=xpos, ypos=ypos, zpos=zpos)

# Calculate linear coefficients

K = linCoeff_cal(R=R)

# Calculate base numbers

n0 = np.floor(2 * K)

# K's from 1 to *no + 1
k_length = 2 * n0 + 1

# Create all possible permutations from 3 first sets of planes

PERMS_number = np.prod(k_length[0:3])

iterables3 = [range(1, int(k_length[0])+1), range(1, int(k_length[1])+1), range(1, int(k_length[2])+1)]
PERMS_J = list(itertools.product(*iterables3))  # list of tuples, each tuples containing 3 int.

print('First intersection calculation: %1d permutations of 3 planes \n' % PERMS_number)

# 3 first sets of planes

I = ([0, 1, 2])

# Start looping over all combinations

W_matrix = np.transpose(R[:, 0:3]/np.tile(np.linalg.norm(R[:, 0:3], axis=0), (3, 1)))

pinv_norm = np.zeros((int(PERMS_number), 1))
intersection_line = np.zeros((3, int(PERMS_number)))

def polla(W_matrix, b_vector, aux):
    Moore_Penrose_solution_check = np.linalg.multi_dot([W_matrix, np.linalg.pinv(W_matrix), b_vector]) - b_vector
    intersection_line[:, aux] = np.dot(np.linalg.pinv(W_matrix), b_vector)[:, 0]
    pinv_norm[aux] = np.linalg.norm(Moore_Penrose_solution_check)

    return intersection_line


for aux, j in enumerate(PERMS_J):

    b_vector = np.zeros((len(I), 1))

    for i in I:
        b_vector[i] = -np.dot(nvec_j(I[i], R), p0_jk(I[i], j[i], R, n0, K))

    # Solution check
    Moore_Penrose_solution_check = np.linalg.multi_dot([W_matrix, np.linalg.pinv(W_matrix), b_vector]) - b_vector
    intersection_line[:, aux] = np.dot(np.linalg.pinv(W_matrix), b_vector)[:, 0]
    pinv_norm[aux] = np.linalg.norm(Moore_Penrose_solution_check)

show3 = False

if show3 is True:
    plt.plot(pinv_norm)
    plt.show()

intersection_line_norm = np.transpose(np.sqrt([np.sum(intersection_line ** 2, axis=0)]))

intersections3_ind = np.where((pinv_norm < mp_tol) & (intersection_line_norm <= 2) & (intersection_line_norm != 0))
intersections3_n = len(intersections3_ind[0])
intersections3 = np.array(PERMS_J)[intersections3_ind[0]]

SURVIVORS = np.zeros((Sn - 2, 1))
SURVIVORS[0] = intersections3_n

intersections_n = intersections3_n
intersections_ind = intersections3_ind
intersections = intersections3

intersections_integers = (
        np.repeat(np.transpose(R)[:, :, np.newaxis], repeats=intersections_n, axis=2)[:, :, None] * np.reshape(
    intersection_line[:, intersections_ind[0]], (3, 1, intersections_n))).sum(axis=1)
intersections_integers = np.reshape(intersections_integers, (np.shape(intersections_integers)[0], intersections_n))

print('Done with first three permutations')
dill.dump_session('JICAMARCA3.pkl')


for ii in range(3, Sn):

    PERMS_J_base = PERMS_J

    # Create all possible permutations from ii first sets of planes with only the surviving set + all new and
    # recursively iterate

    PERMS_number = int(intersections_n * k_length[ii])

    print(
        'Starting plane intersections for new sensor %1d of %1d with %1d permutations on %1d remaining solutions \n' % (
            ii, Sn-1, PERMS_number, intersections_n))

    iterables = [np.array(PERMS_J_base)[intersections_ind[0], :], range(1, int(k_length[ii])+1)]
    PERMS_J = list(itertools.product(*iterables))  #

    I = range(0, ii+1)

    # for aux, j in enumerate(PERMS_J):

    W_matrix = np.transpose(R[:, 0:ii+1] / np.tile(np.linalg.norm(R[:, 0:ii+1], axis=0), (3, 1)))

    pinv_norm = np.zeros((PERMS_number, 1))
    intersection_line = np.zeros((3, PERMS_number))

    PERMS_J_prime = []

    for aux, j in enumerate(PERMS_J):

        PERMS_J_prime.append(np.hstack((j[0], j[1])))

        b_vector = np.zeros((len(I), 1))

        for i in I:

            b_vector[i] = -np.dot(nvec_j(I[i], R), p0_jk(I[i], np.hstack((j[0], j[1]))[i], R, n0, K))

        Moore_Penrose_solution_check = np.linalg.multi_dot([W_matrix, np.linalg.pinv(W_matrix), b_vector]) - b_vector
        intersection_line[:, aux] = np.dot(np.linalg.pinv(W_matrix), b_vector)[:, 0]
        pinv_norm[aux] = np.linalg.norm(Moore_Penrose_solution_check)

    PERMS_J = PERMS_J_prime

    intersections_ind = np.where(pinv_norm < mp_tol)
    intersections_n = len(intersections_ind[0])
    intersections = np.array(PERMS_J)[intersections_ind[0]]

    intersections_integers = (
                np.repeat(np.transpose(R)[:, :, np.newaxis], repeats=intersections_n, axis=2)[:, :, None] * np.reshape(
                intersection_line[:, intersections_ind[0]], (3, 1, intersections_n))).sum(axis=1)
    intersections_integers = np.reshape(intersections_integers, (np.shape(intersections_integers)[0], intersections_n))

    SURVIVORS[ii-2] = intersections_n

intersections_last = intersections_n
intersections_integers_complete = np.vstack((np.zeros(
    (1, np.shape(intersections_integers)[1])), intersections_integers))


k0 = k0(el0=50, az0=270)

cutoff_ph_ang = pi/2

# Find all s-lines that intersect with the cap by range check

cap_intersections_of_slines = slines_intersections(
    k0=k0, intersections_ind = intersections_ind[0], intersection_line=intersection_line, cutoff_ph_ang = cutoff_ph_ang)

# From knowing what lines intercept with cap, find al possible DOA ambigs that are part of this

distance, normal = AmbiguityDistances(intersections_integers_complete=intersections_integers_complete).explicit(intersection_line=intersection_line, intersections_ind=intersections_ind[0], cap_intersections_of_slines=cap_intersections_of_slines, xy=xycoords, k0=k0)

## PLOTS

fig1, ax1 = plt.subplots()
ax1.scatter(xycoords[:, 0] * lambda0, xycoords[:, 1] * lambda0, s = 85, alpha=0.85, marker = 'o', label='Sensor position')
ax1.scatter(xant * lambda0, yant * lambda0, s=40, alpha=1, marker='^', label='Subgrous antennas')
ax1.grid(which='both')
ax1.legend(fontsize=12)
ax1.set_xlabel('x [m]', fontsize=12)
ax1.set_ylabel('y [m]', fontsize=12)
ax1.set_title(r'\textbf{MU-radar sensor configuration}', fontsize=14)
ax1.set_aspect('equal')

# FIXME make it only show integer values in both axis
fig2, ax2 = plt.subplots()
ax2.plot(range(3, Sn+1), SURVIVORS, 'bs')
ax2.grid(which='both')
ax2.set_xlabel('Number of sensors included', fontsize=12)
ax2.set_ylabel('Number of common plane intersections', fontsize=12)
ax2.set_title(r'\textbf{Intersection plane counts}', fontsize=14)

fig3, ax3 = plt.subplots()
ax3.scatter(intersection_line[0, intersections_ind[0]], intersection_line[1, intersections_ind[0]], s=40)
ax3.grid(which='both')
ax3.set_xlabel(r'$s_{x}$ \ [1]', fontsize=12)
ax3.set_ylabel(r'$s_{y}$ \ [1]', fontsize=12)
ax3.set_title(r'\textbf{Intersection lines}', fontsize=14)
ax3.set_aspect('equal')

fig4 = plt.figure()
ax4 = fig4.gca(projection='3d')
for S_ind in range(0, len(intersections_ind[0])):
    print('Starting Sind %1d of %1d \n' % (S_ind, len(intersections_ind[0])))
    s_point = intersection_line[:, intersections_ind[0][S_ind]]
    s_line = np.repeat(np.transpose([s_point]), repeats=100, axis=1)
    s_line[2, :] = np.linspace(start=-np.sqrt(4 - np.dot(s_point, s_point)), stop=np.sqrt(4 - np.dot(s_point, s_point)), num=100, endpoint=True)
    if S_ind == 25:
        ax4.plot(s_line[0, :], s_line[1, :], s_line[2, :], '.r')
    else:
        ax4.plot(s_line[0, :], s_line[1, :], s_line[2, :], '.b')
ax4.set_xlabel(r'$s_{x} \ [1]$', fontsize=12)
ax4.set_ylabel(r'$s_{y} \ [1]$', fontsize=12)
ax4.set_zlabel(r'$s_{z} \ [1]$', fontsize=12)
ax4.set_title(r'\textbf{Solution set $\Omega$}', fontsize=14)



# waveform = AmbiguityDistances(intersections_integers_complete=intersections_integers_complete).wave_form()

plt.show()
print(time()-t)

foo = 1