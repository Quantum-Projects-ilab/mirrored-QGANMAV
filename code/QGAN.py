#!/usr/bin/env python
# coding: utf-8

# # Quantum Generative Adversarial Network

# ## Authors
# 
# 
# <a href="https://carleton.ca/scs/people/michel-barbeau/">Michel Barbeau</a>
# 
# <a href="http://www-public.imtbs-tsp.eu/~garcia_a/web/">Joaquin Garcia-Alfaro</a>
# 
# Version: June 25, 2019

# We reused code from:
# 
# <a href="http://github.com/XanaduAI/pennylane/blob/master/examples/Q3_variational-classifier.ipynb">Example Q3 - Variational classifier - 2. Iris classification</a>
# 
# <a href="http://github.com/XanaduAI/pennylane/blob/master/examples/Q4_quantum-GAN.ipynb">Example Q4 - Quantum Generative Adversarial Network</a>
# 
# <a href="https://pennylane.readthedocs.io/en/latest/tutorials/gaussian_transformation.html">Basic tutorial: Gaussian transformation</a>

# ## Preamble

# <a href="https://pennylane.ai/">PennyLane</a> and other relevant packages are imported.

# In[1]:


import pennylane as qml
from pennylane import numpy as np
from pennylane.optimize import GradientDescentOptimizer
import math
import time


# ## Pre-processing of Real Data

# Read the raw real data, assuming $m$ input files. Each file may contain up to $2^{6}$ single scalar values. Each line comprises a timestamp (not used), a $x$-velocity, a $y$-velocity and a $z$-velocity,

# In[ ]:


# Number of qubits: This number determines the size of the problem, in single data
# items, that can be handled by the program.
num_qubits = 2 # must be greater than one, e.g., 2, 3, 4, 5 or 6
m = 6 # number of real data files
n = 2**num_qubits # number of real values
real_values = np.zeros((m,n))
for i in range(m):
    # read all real data from one file 
    data = np.loadtxt('Parrot_Mambo_Data/realdata'+str(i)+'.txt')
    selected_data = data[:,1:4] # omit the timestamp
    # reshape three-column matrix into a one-rwo array
    selected_data = selected_data.reshape(len(selected_data)*3)
    print("Raw data: ",selected_data)
    # keep the first "n" values
    real_values[i][0:min(n,len(selected_data))] =         selected_data[0:min(n,len(selected_data))]
    print("Raw data: ",real_values[i,:])


# We use probability amplitude encoding, which requires normalized data. Let $x_0,\ldots,x_{n-1}$ be the real data values, their normal form is 
# $$
# x_0/\mu,\ldots,x_{n-1}/\mu
# $$
# where
# $$
# \mu = \sqrt{x_0^2 + \ldots +x_{n-1}^2}.
# $$

# In[ ]:


# Normalization function
def normalize(values):
    mean = np.sqrt(np.sum(values ** 2))
    return  np.array(values / mean)
for i in range(len(real_values)):
   real_values[i,:] = normalize(real_values[i,:]) 
   # check consistency of probability amplitudes
   assert np.abs(1-np.sum(real_values[i,:] ** 2))<=0.0000001
print("Normalized data: ",real_values)


# ## Discriminator
# 
# A "num_qubit"-qubit device is created. With probability amplitude encoding, up to $2^{\mbox{num$\_$qubit}}$ single scalar values can be represented in probability amplitudes in the input circuit quantum state. 

# In[ ]:


dev = qml.device('default.qubit', wires=num_qubits)


# ### Elementary Circuit Layer
# 
# The parameter "W" is a matrix containing the rotation angles applied to the circuit. It has "num_qubits" rows and three colums.

# In[ ]:


def layer(num_wires,W):
    for i in range(num_wires):
       qml.Rot(W[i, 0], W[i, 1], W[i, 2], wires=i)
    for i in range(num_wires):
        qml.CNOT(wires=[i, (i+1)%num_wires])


# ### Quantum  Node for Real Data

# The first parameter, "real_values", is an array that contains the $n$ input real data points. The normalized input data is encoded in the amplitudes of "num_qubits". The second parameter "weights" is a matrix containing the rotation angles applied to the rotation gates. The matrix has one row per layer and "num_qubits" columns. The wire 0 is the output of the circuit. The output ranges in the continuous interval +1 down to -1, respectively corresponding to qubits $\vert 0 \rangle$ and $\vert 1 \rangle$. Intermediate values represent superpositions of qubits $\vert 0 \rangle$ and $\vert 1 \rangle$. The optimizer aims at finding rotation angles such that the output of the circuit is approaching $+1$, which corresponds to qubit $\vert 0 \rangle$.

# In[ ]:


@qml.qnode(dev)
def real_disc_circuit(real_values,weights):
    # initialize the input state real data
    qml.QubitStateVector(real_values,wires=range(num_qubits))
    # assign weights to layers
    for W in weights:
        layer(num_qubits,W)
    # measure 
    return qml.expval.PauliZ(0)


# ## Generator
# 
# The generator produces fake data with entropy, i.e., with uncertainty.
# 
# The fake data can be generated by a qubit-quantum circuit, but it is not usable for perpetrating attacks in the classical data world. Qubit-quantum circuits cannot generate continuous-domain classical data.
# 
# The generator is built using photonic quantum computing and a circuit containing only Gaussian operations that can generate data in a continuous domain. 
# 
# A photonic quantum computing Gaussian device is created:

# In[ ]:


dev_gaussian = qml.device('default.gaussian', wires=2**num_qubits)


# ### Construction of Photonic Quantum Node
# 
# The input on each wire is the vacuum state $\vert 0  >$, i.e., no photon on the wire. The first gate is a displacement gate, with parameter $\alpha$, that phase shift the qumod. The parameter $\alpha$ is a specified in the polar form, as a magnitude (mag_alpha) and as an angle (phase_alpha). This is an active transformation that modifies the photonic energy of the system.
# 
# The second gate rotate the qumode by an angle $\phi$. The measured mean number of photons is $< \hat{a}{\dagger} \hat{a}>$, i.e., the average number of photons in the final state.

# In[ ]:


@qml.qnode(dev_gaussian)
def mean_photon_gaussian(weights):
    for i in range(n):
        qml.Displacement(weights[i][0],weights[i][1], wires=i)
        qml.Rotation(weights[i][2], wires=i)
    #qml.Displacement(params[0][0],params[0][1], wires=1)
    #qml.Rotation(params[0][2], wires=1)
    # return expected numbers of photons on every wire in the final state
    return [qml.expval.MeanPhoton(i) for i in range(2**num_qubits)]


# Using arbitrary displacement and rotation, verify the generator circuit:

# In[ ]:


init_params = 0.1*np.ones([n,3],dtype=float)
mean_photon_gaussian(init_params)


# ## Cost
# 
# ### Probability of Correctly Classifying Real Data
# 
# The output of the discriminator $r$
# is a value in the continuous interval $+1$ down to $−1$, coreesponding to |0⟩ and |1⟩. The output is interpreted as follows. When the output is $+1$, the data is accepted as rrue. When it is −1, the data is rejected and considered fake. The output $r$ is converted to a probability value, in the interval $[0,1]$, using the following conversion:
# $$p_R=\frac{r+1}{2}.$$
# This is called the probability of real true. Parameter "values" is an array of $n$ normalized data points. Parameter "disc_weights" is a matrix of angles used in the discriminator circuit.

# In[ ]:


def prob_real_true(real_values,disc_weights):
    # get measurement
    r = real_disc_circuit(real_values,disc_weights)
    assert(r>=-1 and r<=1)
    # convert "r" to a probability
    p = (r + 1) / 2
    assert(p>=0 and r<=1)
    return p


# ### Probability of Incorrectly Classifying Fake Data
# 
# Similarly, the probability of fake true $p_F$ is calculated using fake values.

# In[ ]:


def prob_fake_true(fake_values,disc_weights):
    # get measurement
    r = real_disc_circuit(fake_values,disc_weights)
    assert(r>=-1 and r<=1)
    # convert "r" to a probability
    p = (r + 1) / 2
    assert(p>=0 and r<=1)
    return p


# ### Discriminator Cost Function
# 
# The discriminator aims to maximize the probability $p_R$
# of accepting true data while minimizing the probability $p_F$ of accepting fake data. During the optimization of the discriminator, the optimizer, being gradient descent, tries to minimize the cost represented by the term $p_F−p_R$.

# In[ ]:


def disc_cost(fake_values,real_values,disc_weights):
    cost = prob_fake_true(fake_values,disc_weights) -         prob_real_true(real_values,disc_weights)
    return cost


# ### Generator Cost Function
# 
# Using a Gaussian device, displacement and rotation angle pairs (in "params") are applied successively to the photonic quantum node. The expected numbers of output photons are measured for each case. Measurement results are stored into variable "fake_values". There is one fake value per probability amplitude, i.e., $2^{6}$.
# 
# The fake values are normalized and applied to the discriminator circuit, using the rotation angles determined during its optimization.

# In[ ]:


def gen_cost(params,disc_weights):
    # calculate expected number of photons
    fake_values = mean_photon_gaussian(params)
    # normalize fake values
    norm_fake_values = normalize(fake_values)
    assert np.abs(1-np.sum(norm_fake_values ** 2))<=0.0000001
    # determine the probability of recognizing them as true values
    cost = - prob_fake_true(norm_fake_values,disc_weights)
    return cost


# ### Initial Circuit Values

# The discriminator circuit is initialized with random rotation angles contained in variable "disc_weights".

# In[ ]:


np.random.seed(0)
num_layers = 2
# discriminator weights
disc_weights = 0.01 * np.random.randn(num_layers, num_qubits, 3)
# test the discriminator circuit
r = real_disc_circuit(real_values[0],disc_weights)
assert(r>=-1 and r<=1)
print("Discriminator expectation (test mode): ", r)


# Create random fake values for discriminator training purposes.

# In[ ]:


fake_values =  0.01 * np.random.randn(n)
# normalized fake values
norm_fake_values = normalize(fake_values)
# check consistency of probability amplitudes
assert np.abs(1-np.sum(norm_fake_values ** 2))<=0.0000001
print("Normalized fake data: ",norm_fake_values)


# Verify cost function:

# In[ ]:


# generator weights
gen_weights = 0.1*np.ones([n,3],dtype=float)
gen_cost(gen_weights,disc_weights)


# ## Discriminator Optimization
# 
# The outcome of the optimization of the discriminator is a matrix of rotation angles (weights) actualizing the discriminator circuit such that the probability that real data is recognized as true is maximized while the probability that fake data is recognized as true is minimized.

# In[ ]:


print("Discriminator optimization...")
steps = 50
# get start time
start = time.time()
# create the optimizer
opt = GradientDescentOptimizer(0.1)
for i in range(steps):
    # pick a random sample
    j = np.random.randint(0,len(real_values))
    disc_weights = opt.step(lambda v: disc_cost(fake_values,real_values[j,:],v),disc_weights)
    cost = disc_cost(fake_values,real_values[j,:],disc_weights)
    #if i % 5 == 0:
        #print("Step {}: cost = {}".format(i+1, cost))
# get time taken 
elapsed_time = time.time()-start 
print("Execution time: ", elapsed_time, " ms")
p_R = prob_real_true(real_values[0,:],disc_weights)
assert(p_R>=0 and p_R<=1)
print("Probability of real true: ", p_R)
p_F = prob_fake_true(fake_values,disc_weights)
print("Probability of fake true (random data): ", p_F)


# ## Generator Optimization
# 
# Perform gradient descent optimization iterations:

# In[ ]:


print("Generator optimization...")
steps = 50
# get start time
start = time.time()# initialize the optimizer
opt = qml.GradientDescentOptimizer(stepsize=0.1)
for i in range(steps):
    # update the circuit parameters
    gen_weights = opt.step(lambda v: gen_cost(v,disc_weights),gen_weights)
    cost = gen_cost(gen_weights,disc_weights)
    #if i % 5 == 0:
    # print("Step {}: cost = {}".format(i+1, cost))
# get time taken 
elapsed_time = time.time()-start 
print("Execution time: ", elapsed_time, " ms")
print("Probability of real true: ", -cost)

