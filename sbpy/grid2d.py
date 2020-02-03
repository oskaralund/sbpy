""" This module contains functions and classes for managing 2D grids. The
conceptual framework used throughout the module is that 2D numpy arrays represent
function evaluations associated to some grid. For example, if F is an Nx-by-Ny
numpy array, then F[i,j] is interpreted as the evaluation of some function F in
an associated grid node (x_ij, y_ij). 2D numpy arrays representing function
evaluations on a grid are called 'grid functions'. We refer to the boundaries of
a grid function as 's' for south, 'e' for east, 'n' for north, and 'w' for west.
More precisely the boundaries of a grid function F are

    South: F[:,0]
    East:  F[-1,:]
    North: F[:,-1]
    West:  F[0,:]

"""

import itertools
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rc
rc('text', usetex=True)

def get_boundary(X,Y,side):
    """ Returns the boundary of a block. """

    assert(side in {'w','e','s','n'})

    if side == 'w':
        return X[0,:], Y[0,:]
    elif side == 'e':
        return X[-1,:], Y[-1,:]
    elif side == 's':
        return X[:,0], Y[:,0]
    elif side == 'n':
        return X[:,-1], Y[:,-1]

def get_function_boundary(F,side):
    """ Returns the boundary of a function evaluated on a 2D grid. """

    assert(side in {'w','e','s','n'})

    if side == 'w':
        return F[0,:]
    elif side == 'e':
        return F[-1,:]
    elif side == 's':
        return F[:,0]
    elif side == 'n':
        return F[:,-1]

def get_boundary_slice(F,side):
    """ Get a slice representing the boundary of a grid function. The slice can
    be used to index the given boundary of the grid function. For example, if
    slice = get_boundary_slice(F,'w'), then F[slice] will refer to the western
    boundary of F.

    Args:
        F: A grid function.
        side: The side at which the boundary is located ('s', 'e', 'n', or 'w')

    Returns:
        slice: A slice that can be used to index the given boundary in F.
    """
    assert(side in ['s', 'e', 'n', 'w'])
    (Nx, Ny) = F.shape
    slice_dict = {'s': (slice(Nx), 0),
                  'e': (-1, slice(Ny)),
                  'n': (slice(Nx), -1),
                  'w': (0, slice(Ny))}

    return slice_dict[side]



def get_corners(X,Y):
    """ Returns the corners of a block.

    Starts with (X[0,0], Y[0,0]) and continues counter-clockwise.
    """
    return np.array([[X[0,0]  , Y[0,0]  ],
                     [X[-1,0] , Y[-1,0] ],
                     [X[-1,-1], Y[-1,-1]],
                     [X[0,-1] , Y[0,-1]]])


def get_center(X,Y):
    """ Returns the center point of a block. """
    corners = get_corners(X,Y)
    return 0.25*(corners[0] + corners[1] + corners[2] + corners[3])


class Multiblock:
    """ Represents a structured multiblock grid.

    Attributes:
        blocks: A list of pairs of 2D numpy arrays containing x- and y-values for
                each block.

        corners: A list of unique corners in the grid.

        edges: A list pairs of indices to the corners list, defining all the
               unique edges in grid connectivity graph.

        faces: A list of index-quadruples defining the blocks. For example, if
               faces[n] = [i,j,k,l], and (X,Y) are the matrices corresponding to
               block n, then (X[0,0],Y[0,0]) = corners[i]
                             (X[-1,0],Y[-1,0]) = corners[j]
                             (X[-1,-1],Y[-1,-1]) = corners[k]
                             (X[0,-1],Y[0,-1]) = corners[l]

        face_edges: A list of dicts specifying the edges of each face in the
                    grid connectivity graph. For example, if
                    face_edges[n] = {'s': 1, 'e': 5, 'n': 3, 'w': 0}, then the
                    southern boundary of the n:th face is edge 1, and so on.

        interfaces: A list of dictionaries containing the interfaces for each
                    block. For example, if interfaces[i] = {'n': (j, 'w')}, then
                    the northern boundary of the block i coincides with the
                    western boundary of the western boundary of block j.

        non_interfaces: A list of lists specifying the non-interfaces of each
                        block. For example, if non_interfaces[i] = ['w', 'n'],
                        then the western and northern sides of block i are not
                        interfaces.

        num_blocks: The total number of blocks in the grid.

        Nx: A list of the number of grid points in the x-direction of each block.

        Ny: A list of the number of grid points in the y-direction of each block.
    """

    def __init__(self, blocks):
        """ Initializes a Multiblock object.

        Args:
            blocks: A list of pairs of 2D numpy arrays containing x- and y-values
                   for each block.

            Note that the structure of these blocks should be such that for the
            k:th element (X,Y) in the blocks list, we have that (X[i,j],Y[i,j])
            is the (i,j):th node in the k:th block.
        """

        for (X,Y) in blocks:
            assert(X.shape == Y.shape)

        self.blocks = blocks
        self.num_blocks = len(blocks)

        self.shapes = []
        for (X,Y) in blocks:
            self.shapes.append((X.shape[0], X.shape[1]))

        # Save unique corners
        self.corners = []
        for X,Y in self.blocks:
            self.corners.append(get_corners(X,Y))

        self.corners = np.unique(np.concatenate(self.corners), axis=0)

        # Save faces in terms of unique corners
        self.faces = []

        for k,(X,Y) in enumerate(self.blocks):
            block_corners = get_corners(X,Y)
            indices = []
            for c in block_corners:
                idx = np.argwhere(np.all(c == self.corners, axis=1)).item()
                indices.append(idx)
            self.faces.append(np.array(indices))
        self.faces = np.array(self.faces)

        # Save unique edges
        self.edges = []
        for face in self.faces:
            for k in range(4):
                self.edges.append(np.array(sorted([face[k], face[(k+1)%4]])))

        self.edges = np.unique(self.edges, axis=0)

        # Save face edges
        self.face_edges = []
        for face in self.faces:
            self.face_edges.append({})
            for k,side in enumerate(['s','e','n','w']):
                edge = np.array(sorted([face[k], face[(k+1)%4]]))
                self.face_edges[-1][side] = \
                    np.argwhere(np.all(edge == self.edges, axis=1)).item()

        # Find interfaces
        self.interfaces = [{} for _ in range(self.num_blocks)]
        for ((i,edges1), (j,edges2)) in \
        itertools.combinations(enumerate(self.face_edges),2):
            for (side1,side2) in \
            itertools.product(['s', 'e', 'n', 'w'], repeat=2):
                if edges1[side1] == edges2[side2]:
                    self.interfaces[i][side1] = (j, side2)
                    self.interfaces[j][side2] = (i, side1)

        # Find non-interfaces
        self.non_interfaces = [[] for _ in range(self.num_blocks)]
        for (i,edges) in enumerate(self.face_edges):
            is_interface = False
            other_edges = \
                np.array([ np.fromiter(other_edges.values(), dtype=float) for
                    (j, other_edges) in enumerate(self.face_edges) if j != i])
            for side in ['s', 'e', 'n', 'w']:
                if edges[side] not in other_edges.flatten():
                    self.non_interfaces[i].append(side)


    def evaluate_function(self, f):
        """ Evaluates a (vectorized) function on the grid. """
        return [ f(X,Y) for (X,Y) in self.blocks ]


    def get_blocks(self):
        return self.blocks


    def get_shapes(self):
        """ Returns a list of the shapes of the blocks in the grid. """
        return self.shapes


    def is_interface(self, block_idx, side):
        """ Check if a given side is an interface.

        Returns True if the given side of the given block is an interface. """

        if side in self.interfaces[block_idx]:
            return True
        else:
            return False


    def plot_grid(self):
        """ Plot the entire grid. """

        fig, ax = plt.subplots()
        for X,Y in self.blocks:
            ax.plot(X,Y,'b')
            ax.plot(np.transpose(X),np.transpose(Y),'b')
            for side in {'w', 'e', 's', 'n'}:
                x,y = get_boundary(X,Y,side)
                ax.plot(x,y,'k',linewidth=3)

        plt.show()


    def plot_domain(self):
        """ Fancy domain plot without gridlines. """

        fig, ax = plt.subplots()
        for k,(X,Y) in enumerate(self.blocks):
            xs,ys = get_boundary(X,Y,'s')
            xe,ye = get_boundary(X,Y,'e')
            xn,yn = get_boundary(X,Y,'n')
            xn = np.flip(xn)
            yn = np.flip(yn)
            xw,yw = get_boundary(X,Y,'w')
            xw = np.flip(xw)
            yw = np.flip(yw)
            x_poly = np.concatenate([xs,xe,xn,xw])
            y_poly = np.concatenate([ys,ye,yn,yw])

            ax.fill(x_poly,y_poly,'tab:gray')
            ax.plot(x_poly,y_poly,'k')
            c = get_center(X,Y)
            ax.text(c[0], c[1], "$\Omega_" + str(k) + "$")


        plt.show()


    def get_neighbor_boundary(self, F, block_idx, side):
        """ Returns an array of boundary data from a neighboring block.

        Arguments:
            F: A 2d array of function evaluations on the neighbor block.
            block_idx: The index of the block to send data to.
            side: The side of the block to send data to ('s', 'e', 'n', or 'w').
        """
        assert(self.is_interface(block_idx, side))

        neighbor_idx, neighbor_side = self.interfaces[block_idx][side]

        flip = False
        if (neighbor_side, side) in [('s','e'), ('s','s'),
                                   ('e','s'), ('e','e'),
                                   ('n','w'), ('n','n'),
                                   ('w','n'), ('w','w')]:
            flip = True

        if flip:
            return np.flip(get_function_boundary(F, neighbor_side))
        else:
            return get_function_boundary(F, neighbor_side)


def load_p3d(filename):
    with open(filename) as data:
        num_blocks = int(data.readline())

        X = []
        Y = []
        Nx = []
        Ny = []
        for _ in range(num_blocks):
            size = np.fromstring(data.readline(), sep=' ', dtype=int)
            Nx.append(size[0])
            Ny.append(size[1])

        blocks = []
        for k in range(num_blocks):
            X_cur = []
            Y_cur = []
            for n in range(Nx[k]):
                X_cur.append(np.fromstring(data.readline(), sep=' '))
            for n in range(Nx[k]):
                Y_cur.append(np.fromstring(data.readline(), sep=' '))

            blocks.append((np.array(X_cur),np.array(Y_cur)))
            #X.append(np.array(X_cur))
            #Y.append(np.array(Y_cur))
            for _ in range(Nx[k]):
                next(data)


    return blocks


