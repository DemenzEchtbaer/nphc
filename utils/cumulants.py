import numpy as np
from numba import autojit, jit, double, int32, int64, float64
from joblib import Parallel, delayed


class SimpleHawkes(object):

    def __init__(self, N=[], sort_process=False):
        self.dim = len(N)
        if sort_process:
            self.N = []
            for i, process in enumerate(N):
                self.N.append(np.sort(N[i]))
        else:
            self.N = N
        self.L = np.empty(self.dim)
        self.time = max([x[-1] for x in N if x is not None and len(x) > 0]) * (self.dim > 0)
        self.set_L()

    def set_L(self):
        if self.dim > 0:
            for i, process in enumerate(self.N):
                if process is None:
                    self.L[i] = 0
                else:
                    self.L[i] = len(process) / self.time


class Cumulants(SimpleHawkes):

    def __init__(self,N=[],hMax=40.):
        super().__init__(N)
        self.C = None
        self.C_th = None
        self.K = None
        self.K_th = None
        self.K_part = None
        self.K_part_th = None
        self.R_true = None
        self.hMax = hMax
        self.H = None

    #########
    ## Functions to compute third order cumulant
    ##  with new formula
    ##
    ## Implementation with classic formula is below
    #########

    @autojit
    def set_F(self,H=0.):
        if H == 0.:
            hM = self.hMax
        else:
            hM = H
        d = self.dim
        K = np.zeros((d,d,d))
        for i in range(d):
            for j in range(d):
                for k in range(d):
                    K[i,j,k] = E_ijk(self.N[i],self.N[j],self.N[k],-hM,hM,self.time,self.L[i],self.L[j],self.L[k]) - self.L[k]*(2*hM*A_ij(self.N[i],self.N[j],-2*hM,2*hM,self.time,self.L[i],self.L[j]) - 2*I_ij(self.N[i],self.N[j],2*hM,self.time,self.L[i],self.L[j]))
        self.F = K.copy()
        self.F += np.einsum('jki',K)
        self.F += np.einsum('kij',K)
        self.F /= 3

    @autojit
    def set_F_c(self,H=0.):
        if H == 0.:
            hM = self.hMax
        else:
            hM = H
        d = self.dim
        self.F_c = np.zeros((d,d))
        for i in range(d):
            for j in range(d):
                self.F_c[i,j] = 2 * ( E_ijk(self.N[j],self.N[i],self.N[j],-hM,hM,self.time,self.L[j],self.L[i],self.L[j]) - self.L[j]*(2*hM*A_ij(self.N[i],self.N[j],-2*hM,2*hM,self.time,self.L[i],self.L[j]) - I_ij(self.N[j],self.N[i],2*hM,self.time,self.L[j],self.L[i]) ) )
                self.F_c[i,j] += E_ijk(self.N[j],self.N[j],self.N[i],-hM,hM,self.time,self.L[j],self.L[j],self.L[i]) - self.L[i]*(2*hM*A_ij(self.N[j],self.N[j],-2*hM,2*hM,self.time,self.L[j],self.L[j])  - 2*I_ij(self.N[j],self.N[j],2*hM,self.time,self.L[j],self.L[j]))
        self.F_c /= 3

    #########
    ## Functions to compute third order cumulant with
    ##  classic formula
    #########
    #@autojit
    def set_B(self,H=0.,method='parallel'):
        if H == 0.:
            hM = self.hMax
        else:
            hM = abs(H)
        d = self.dim
        if method == 'classic':
            self.B = np.zeros((d,d))
            for i in range(d):
                for j in range(d):
                    self.B[i,j] = A_ij(self.N[i],self.N[j],-hM,0,self.time,self.L[i],self.L[j])
        elif method == 'parallel':
            l = Parallel(-1)(delayed(A_ij)(self.N[i],self.N[j],-hM,0,self.time,self.L[i],self.L[j]) for i in range(d) for j in range(d))
            self.B = np.array(l).reshape(d,d)
        # we keep the symmetric part to remove edge effects
        self.B[:] = 0.5 * (self.B + self.B.T)

    #@autojit
    def set_C(self,H=0.,compute_C=False,method='parallel'):
        if H == 0.:
            hM = self.hMax
        else:
            hM = H
        d = self.dim
        if compute_C:
            if method == 'classic':
                self.C = np.zeros((d,d))
                for i in range(d):
                    for j in range(d):
                        self.C[i,j] = A_ij(self.N[i],self.N[j],-hM,hM,self.time,self.L[i],self.L[j])
            elif method == 'parallel':
                l = Parallel(-1)(delayed(A_ij)(self.N[i],self.N[j],-hM,hM,self.time,self.L[i],self.L[j]) for i in range(d) for j in range(d))
                self.C = np.array(l).reshape(d,d)
            # we keep the symmetric part to remove edge effects
            self.C[:] = 0.5*(self.C + self.C.T)
        else:
            assert self.B is not None, "You should first set B using the function 'set_B'."
            self.C = 2*self.B + np.diag(self.L)

    #@autojit
    def set_E(self,H=0.,method='parallel'):
        if H == 0.:
            hM = self.hMax
        else:
            hM = H
        d = self.dim
        if method == 'classic':
            self.E = np.zeros((d,d,d))
            for i in range(d):
                for j in range(d):
                    for k in range(d):
                        self.E[i,j,k] = E_ijk(self.N[i],self.N[j],self.N[k],-hM,0,self.time,self.L[i],self.L[j],self.L[k])
        elif method == 'parallel':
            l = Parallel(-1)(delayed(E_ijk)(self.N[i],self.N[j],self.N[k],-hM,0,self.time,self.L[i],self.L[j],self.L[k]) for i in range(d) for j in range(d) for k in range(d))
            self.E = np.array(l).reshape(d,d,d)

    #@autojit
    def set_J(self, H=0.,method='parallel'):
        if H == 0.:
            hM = self.hMax
        else:
            hM = H
        d = self.dim
        if method == 'classic':
            self.J = np.zeros((d,d))
            for i in range(d):
                for j in range(d):
                    self.J[i,j] = I_ij(self.N[i],self.N[j],hM,self.time,self.L[i],self.L[j])
        elif method == 'parallel':
            l = Parallel(-1)(delayed(I_ij)(self.N[i],self.N[j],hM,self.time,self.L[i],self.L[j]) for i in range(d) for j in range(d) )
            self.J = np.array(l).reshape(d,d)
        # we keep the symmetric part to remove edge effects
        self.J[:] = 0.5 * (self.J + self.J.T)

    #@autojit
    def set_E_c(self,H=0.,method='parallel'):
        if H == 0.:
            hM = self.hMax
        else:
            hM = H
        d = self.dim
        if method == 'classic':
            self.E_c = np.zeros((d,d))
            for i in range(d):
                for j in range(d):
                    self.E_c[i,j] = E_ijk(self.N[i],self.N[j],self.N[j],-hM,0,self.time,self.L[i],self.L[j],self.L[j])
        elif method == 'parallel':
            l = Parallel(-1)(delayed(E_ijk)(self.N[i],self.N[j],self.N[j],-hM,0,self.time,self.L[i],self.L[j],self.L[j]) for i in range(d) for j in range(d))
            self.E_c = np.array(l).reshape(d,d)

    #@autojit
    def set_H(self,method=0,N=1000):
        """
        Set the matrix parameter self.H using different heuristics.
        Method 0 simply set the same H for each couple (i,j).
        Method 1 set the H that minimizes 1/H \int_0^H u c_{ij} (u) du.
        """
        d = self.dim
        if method == 0:
            self.H = self.hMax * np.ones((d,d))
        if method == 1:
            self.H = np.empty((d,d))
            for i in range(d):
                for j in range(d):
                    range_h = np.logspace(-3,3,N)
                    res = []
                    for h in range_h:
                        val = I_ij(self.N[i],self.N[j],h,self.time,self.L[i],self.L[j]) / h
                        res.append(val)
                    res = np.array(res)
                    self.H[i,j] = range_h[np.argmin(res)]

    def set_R_true(self,R_true):
        self.R_true = R_true

    def set_K(self,H=0.,method='classic'):
        if H == 0.:
            hM = self.hMax
        else:
            hM = H
        if method == 'classic':
            assert self.B is not None, "You should first set B using the function 'set_B'."
            assert self.E is not None, "You should first set E using the function 'set_E'."
            assert self.J is not None, "You should first set J using the function 'set_J'."
            assert self.C is not None, "You should first set C using the function 'set_C'."
            self.K = get_K(self.B,self.E,self.J,self.C,self.L,hM)
        elif method == 'new':
            self.set_F(H)
            self.K = self.F

    def set_K_part(self,H=0.,method='classic'):
        if H == 0.:
            hM = self.hMax
        else:
            hM = H
        if method == 'classic':
            if self.K_part is None:
                assert self.B is not None, "You should first set B using the function 'set_B'."
                assert self.E_c is not None, "You should first set E using the function 'set_E_c'."
                assert self.J is not None, "You should first set J using the function 'set_J'."
                assert self.C is not None, "You should first set C using the function 'set_C'."
                self.K_part = get_K_part(self.B,self.E_c,self.J,self.C,self.L,hM)
            else:
                self.set_B(hM)
                self.set_C(hM)
                self.set_E_c(hM)
                self.set_J(hM)
        elif method == 'new':
            self.set_F_c(H)
            self.K_part = self.F_c

    def set_C_th(self):
        assert self.R_true is not None, "You should provide R_true."
        self.C_th = get_C_th(self.L, self.R_true)

    def set_K_th(self):
        assert self.R_true is not None, "You should provide R_true."
        assert self.C_th is not None, "You should provide C_th to set_ K_th."
        self.K_th = get_K_th(self.L,self.C_th,self.R_true)

    def set_K_part_th(self):
        assert self.R_true is not None, "You should provide R_true."
        self.K_part_th = get_K_part_th(self.L,self.C_th,self.R_true)

    def set_all(self,H=0.):
        print("Starting computation of full cumulants...")
        self.set_B(H)
        print("cumul.B is computed !")
        self.set_C(H)
        print("cumul.C is computed !")
        self.set_E(H)
        print("cumul.E is computed !")
        self.set_J(H)
        print("cumul.J is computed !")
        self.set_K(H)
        print("cumul.K is computed !")
        print("All cumulants are computed !")

    def set_all_part(self,H=0.):
        print("Starting computation of partial cumulants...")
        self.set_B(H)
        print("cumul.B is computed !")
        self.set_C(H)
        print("cumul.C is computed !")
        self.set_E_c(H)
        print("cumul.E_c is computed !")
        self.set_J(H)
        print("cumul.J is computed !")
        self.set_K_part(H)
        print("cumul.K_part is computed !")
        print("All cumulants are computed !")


###########
## Empirical cumulants with formula from the paper
###########
@autojit
def get_K(B,E,J,C,L,H):
    I = np.eye(len(L))
    M = np.einsum('k,ij->ijk',L,H*C-2*J)
    K1 = E-M
    K1 += np.einsum('ij,jk->ijk',I,B)
    K = K1.copy()
    K += np.einsum('jki',K1)
    K += np.einsum('kij',K1)
    K += np.einsum('ij,ik,i->ijk',I,I,L)
    return K

@autojit
def get_K_part(B,E_c,J,C,L,H):
    K_part = B.T
    K_part += np.diag(L)
    K_part += 2*np.diag(np.diag(B))
    M_c = np.einsum('j,ij->ij',L,H*C-2*J)
    K_part += 2*(E_c-M_c)
    K_part += (E_c-M_c).T
    return K_part


##########
## Theoretical cumulants C, K, K_part
##########
@autojit
def get_C_th(L, R):
    return np.dot(R,np.dot(np.diag(L),R.T))

@autojit
def get_K_th(L,C,R):
    d = len(L)
    if R.shape[0] == d**2:
        R_ = R.reshape(d,d)
    else:
        R_ = R.copy()
    K1 = np.einsum('im,jm,km->ijk',C,R_,R_)
    K = K1.copy()
    K += np.einsum('jki',K1)
    K += np.einsum('kij',K1)
    K -= 2*np.einsum('m,im,jm,km->ijk',L,R_,R_,R_)
    return K

@autojit
def get_K_part_th(L,C,R):
    d = len(L)
    if R.shape[0] == d**2:
        R_ = R.reshape(d,d)
    else:
        R_ = R.copy()
    K_part = np.dot(R*R,C.T)
    K_part += 2*np.dot(R_*(C-np.dot(R_,np.diag(L))),R_.T)
    return K_part


##########
## Useful fonctions to set_ empirical integrated cumulants
##########
#@jit(double(double[:],double[:],int32,int32,double,double,double), nogil=True, nopython=True)
#@jit(float64(float64[:],float64[:],int64,int64,int64,float64,float64), nogil=True, nopython=True)
@autojit
def A_ij(Z_i,Z_j,a,b,T,L_i,L_j):
    """

    Computes the mean centered number of jumps of N^j between \tau + a and \tau + b, that is

    \frac{1}{T} \sum_{\tau \in Z^i} ( N^j_{\tau + b} - N^j_{\tau + a} - \Lambda^j (b - a) )

    """
    res = 0
    u = 0
    count = 0
    n_i = Z_i.shape[0]
    n_j = Z_j.shape[0]
    for t in range(n_i):
        tau = Z_i[t]
        if tau + a < 0: continue
        while u < n_j:
            if Z_j[u] <= tau + a:
                u += 1
            else:
                break
        if u == n_j: continue
        v = u
        while v < n_j:
            if Z_j[v] < tau + b:
                v += 1
            else:
                break
        if v < n_j:
            if u > 0:
                count += 1
                res += v-u
    if count < n_i:
        if count > 0:
            res *= n_i * 1. / count
    res /= T
    res -= (b - a) * L_i * L_j
    return res

@autojit
def E_ijk(Z_i,Z_j,Z_k,a,b,T,L_i,L_j,L_k):
    """

    Computes the mean of the centered product of i's and j's jumps between \tau + a and \tau + b, that is

    \frac{1}{T} \sum_{\tau \in Z^k} ( N^i_{\tau + b} - N^i_{\tau + a} - \Lambda^i * ( b - a ) )
                                  * ( N^j_{\tau + b} - N^j_{\tau + a} - \Lambda^j * ( b - a ) )

    """
    res = 0
    u = 0
    x = 0
    count = 0
    n_i = Z_i.shape[0]
    n_j = Z_j.shape[0]
    n_k = Z_k.shape[0]
    trend_i = L_j*(b-a)
    trend_j = L_j*(b-a)
    for t in range(n_k):
        tau = Z_k[t]
        if tau + a < 0: continue
        # work on Z_i
        while u < n_i:
            if Z_i[u] <= tau + a:
                u += 1
            else:
                break
        v = u
        while v < n_i:
            if Z_i[v] < tau + b:
                v += 1
            else:
                break
        # work on Z_j
        while x < n_j:
            if Z_j[x] <= tau + a:
                x += 1
            else:
                break
        y = x
        while y < n_j:
            if Z_j[y] < tau + b:
                y += 1
            else:
                break
        # check if this step is admissible
        if y < n_j and x > 0 and v < n_i and u > 0:
            count += 1
            res += (v-u-trend_i) * (y-x-trend_j)
    if count < n_k and count > 0:
        res *= n_k * 1. / count
    res /= T
    return res

@autojit
def I_ij(Z_i,Z_j,H,T,L_i,L_j):
    """

    Computes the integral \int_{(0,H)} t c^{ij} (t) dt. This integral equals

    \sum_{\tau \in Z^i} \sum_{\tau' \in Z^j} (\tau - \tau') 1_{ \tau - H < \tau' < \tau } - H^2 / 2 \Lambda^i \Lambda^j

    """
    n_i = Z_i.shape[0]
    n_j = Z_j.shape[0]
    res = 0
    u = 0
    count = 0
    for t in range(n_i):
        tau = Z_i[t]
        tau_minus_H = tau - H
        if tau_minus_H  < 0: continue
        while u < n_j:
            if Z_j[u] <= tau_minus_H :
                u += 1
            else:
                break
        v = u
        while v < n_j:
            tau_minus_tau_p = tau - Z_j[v]
            if tau_minus_tau_p > 0:
                res += tau_minus_tau_p
                count += 1
                v += 1
            else:
                break
    if count < n_i and count > 0:
        res *= n_i * 1. / count
    res /= T
    res -= .5 * (H**2) * L_i * L_j
    return res


if __name__ == "__main__":
    N = [np.sort(np.random.randint(0,100,size=20)),np.sort(np.random.randint(0,100,size=20))]
    cumul = Cumulants(N,hMax=10)
    cumul.set_all()
    cumul.set_all_part()
    print("cumul.C = ")
    print(cumul.C)
    print("cumul.J = ")
    print(cumul.J)