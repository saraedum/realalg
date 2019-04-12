
''' A module for representing and manipulating real algebraic numbers and the fields that they live in. '''

from fractions import Fraction
from functools import total_ordering
from math import log10 as log
from numbers import Integral

import cypari as cp
import sympy as sp

from .interval import Interval

sp_x = sp.Symbol('x')
cp_x = cp.pari('x')

def log_plus(x):
    ''' Return the height of the number ``x``. '''
    return log(max(1, abs(x)))

def sp_polynomial(coefficients):
    ''' Return the sympy polynomial with the given coefficients. '''
    return sp.Poly(coefficients[::-1], sp_x)

def cp_polynomial(coefficients):
    ''' Return the cypari polynomial with the given coefficients. '''
    return cp.pari(' + '.join('{}*x^{}'.format(coefficient, index) for index, coefficient in enumerate(coefficients)))

class RealNumberField(object):
    ''' Represents the NumberField QQ(lmbda) = QQ[x] / << f(x) >> where lmbda is a real root of f(x). '''
    def __init__(self, coefficients, index=-1):  # List of integers and / or Fractions, integer index
        self.coefficients = [Fraction(coefficient) for coefficient in coefficients]
        self.index = index
        self.sp_polynomial = sp_polynomial(self.coefficients)
        self.cp_polynomial = cp_polynomial(self.coefficients)
        if not self.cp_polynomial.polisirreducible():
            raise ValueError('Polynomial {} is reducible'.format(self.cp_polynomial))
        self.degree = self.cp_polynomial.poldegree()
        self.length = sum(log_plus(coefficient.numerator) + log_plus(coefficient.denominator) for coefficient in self.coefficients)
        real_roots = self.sp_polynomial.real_roots()
        if not real_roots:
            raise ValueError('Polynomial {} has no real roots'.format(self.cp_polynomial))
        self.sp_place = real_roots[index]
        self.lmbda = self([0, 1])
        self._precision = 0
        self._intervals = None
        self._bound = max(len(str(abs(int(self.sp_place**i)))) for i in range(self.degree))
    
    def __str__(self):
        return 'QQ(x) / <<{}>> embedding x |--> {}'.format(self.cp_polynomial, self.lmbda)
    def __repr__(self):
        return str(self)
    def __call__(self, coefficients):
        return RealAlgebraic.from_coefficients(self, coefficients)
    def __hash__(self):
        return hash(tuple(self.coefficients) + (self.index,))
    
    def intervals(self, precision):
        ''' Return intervals around self.lmbda**i that are all correct to at least ``precision`` digits. '''
        assert isinstance(precision, Integral)
        assert precision > 0
        if precision > self._precision:
            self._precision = precision
            working_precision = precision + self.degree*self._bound + 1
            s = str(sp.N(self.sp_place, working_precision))
            # TODO: deal with e notation.
            I = Interval.from_string(s, working_precision)
            self._intervals = [I**i for i in range(self.degree)]
        return [I.simplify(precision) for I in self._intervals]

@total_ordering
class RealAlgebraic(object):
    ''' Represents an element of a number field. '''
    def __init__(self, field, cp_mod):
        self.field = field
        self.cp_mod = cp_mod
        self.cp_polynomial = self.cp_mod.lift()
        self.len = self.cp_polynomial.poldegree()
        self.coefficients = [Fraction(int(self.cp_polynomial.polcoeff(i).numerator()), int(self.cp_polynomial.polcoeff(i).denominator())) for i in range(self.len+1)]
        if not self.coefficients:
            self.coefficients = [Fraction(0, 1)]
        self.length = sum(log_plus(coefficient.numerator) + log_plus(coefficient.denominator) + index * self.field.length for index, coefficient in enumerate(self.coefficients))
    @classmethod
    def from_coefficients(cls, field, coefficients):
        ''' Return the element of the field with the given coefficients. '''
        return cls(field, cp_polynomial(coefficients).Mod(field.cp_polynomial))
    @classmethod
    def from_rational(cls, field, rational):
        ''' Return the element of QQ within the given field. '''
        return cls(field, cp_polynomial([rational]).Mod(field.cp_polynomial))
    def __str__(self):
        return str(self.N())
    def __repr__(self):
        return str(self)
    def __add__(self, other):
        if isinstance(other, RealAlgebraic):
            return RealAlgebraic(self.field, self.cp_mod + other.cp_mod)
        elif isinstance(other, (Fraction, Integral)):
            return self + RealAlgebraic.from_rational(self.field, other)
        else:
            return NotImplemented
    def __radd__(self, other):
        return self + other
    def __sub__(self, other):
        return self + (-other)
    def __neg__(self):
        return RealAlgebraic(self.field, -self.cp_mod)
    def __mul__(self, other):
        if isinstance(other, RealAlgebraic):
            return RealAlgebraic(self.field, self.cp_mod * other.cp_mod)
        elif isinstance(other, (Fraction, Integral)):
            return self * RealAlgebraic.from_rational(self.field, other)
        else:
            return NotImplemented
    def __rmul__(self, other):
        return self * other
    def __div__(self, other):
        return self.__truediv__(other)
    def __floordiv__(self, other):
        # Can do this much more efficiently.
        return int(self / other)
    def __truediv__(self, other):
        if other == 0:
            raise ZeroDivisionError('division by zero')
        if isinstance(other, RealAlgebraic):
            return RealAlgebraic(self.field, self.cp_mod / other.cp_mod)
        elif isinstance(other, (Fraction, Integral)):
            return self / RealAlgebraic.from_rational(self.field, other)
        else:
            return NotImplemented
    def __rdiv__(self, other):
        return self.__rtruediv__(other)
    def __rtruediv__(self, other):
        if isinstance(other, (Fraction, Integral)):
            return RealAlgebraic.from_rational(self.field, other) / self
        else:
            return NotImplemented
    def __mod__(self, other):
        if isinstance(other, Integral):
            return self - int(self / other) * other
        else:
            return NotImplemented
    def __pow__(self, other):
        if isinstance(other, Integral):
            return RealAlgebraic(self.field, self.cp_mod ** other)
        else:
            return NotImplemented
    
    def minpoly(self):
        ''' Return the (cypari) minimum polynomial of this algebraic number. '''
        return self.cp_mod.minpoly()
    def degree(self):
        ''' Return the degree of this algebraic number. '''
        return self.minpoly().poldegree()
    
    def interval(self, precision=8):
        ''' Return an interval around self that is correct to at least ``precision`` digits. '''
        working_precision = int(precision + self.length + 1)
        intervals = self.field.intervals(working_precision)
        coeffs = [Interval.from_fraction(coeff, working_precision) for coeff in self.coefficients]
        interval = sum(coeff * interval for coeff, interval in zip(coeffs, intervals))
        return interval.simplify(precision)
    def N(self, precision=8):
        ''' Return a string approximating self to at least ``precision`` digits. '''
        return self.interval(precision).midpoint()
    def __int__(self):
        return int(self.interval(2*int(self.length+1)))
    def __float__(self):
        return float(self.N(64))
    def sign(self):
        ''' Return the sign of this real number. '''
        return self.interval(2*int(self.length+1)).sign()
    def __eq__(self, other):
        return (self - other).sign() == 0
    def __gt__(self, other):
        return (self - other).sign() == +1
    def __hash__(self):
        return hash(tuple(self.coefficients))

