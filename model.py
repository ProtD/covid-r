from collections import namedtuple
import numpy as np
import pandas as pd

def frange(x, y, jump):
    while x <= y + 0.00001 * jump:
        yield x
        x += jump

Variable = namedtuple("Variable", ["name", "min", "max", "step", "default", "getter", "cat"])
variables = {
    "r0": Variable(
        dict(en="Basic reproduction number (R0)", cs="Základní reprodukční číslo (R0)"),
        1.0, 5.0, 0.1, 2.0, lambda x: x.r0, 0,
    ),
    "testing_rate": Variable(
        dict(en="Symptomatics tested (%)", cs="Testováno lidí s příznaky (%)"),
        0, 100, 5, 50, lambda x: x.testing_rate, 1,
    ),
    "testing_delay": Variable(
        dict(en="Testing delay (days)", cs="Prodleva testování (dny)"),
        0, 10, 1, 3, lambda x: x.testing_delay, 1,
    ),
    "isolation_effectivity": Variable(
        dict(en="Isolation effectivity (%)", cs="Efektivita izolace"),
        0, 100, 5, 90, lambda x: x.isolation_effectivity, 1,
    ),
    "tracing_rate": Variable(
        dict(en="Contacts successfully traced (%)", cs="Úspěšně trasováno kontaktů (%)"),
        0, 100, 5, 0, lambda x: x.tracing_rate, 1,
    ),
    "tracing_delay": Variable(
        dict(en="Contact tracing delay (days)", cs="Prodleva trasování"),
        0, 10, 1, 1, lambda x: x.tracing_delay, 1,
    ),
    "asymptomatic_inf": Variable(
        dict(en="Relative infectiousness of asymptomatics (%)", cs="Relativní infekčnost lidí bez příznaků (%)"),
        0, 100, 5, 20, lambda x: x.asymptomatic_inf, 2,
    ),
}

class Infection(object):
    r0 = 3.0
    infection_rates = [0, 1, 3, 6, 8,  6,  3,  1]
    symptoms = [0, 0, 0, 0, 10, 20, 20, 10]

    testing_rate = None
    testing_delay = None
    isolation_effectivity = None
    tracing_rate = None
    tracing_delay = None
    asymptomatic_inf = None
    
    def set(self, var, value):
        pass
    
    def set_rates(self, r0=None, infection_rates=None, symptoms=None):
        "Sets R0, daily infection rates and daily symptom onsets."
        self.r0 = r0 or self.r0
        self.infection_rates = np.array(infection_rates or list(self.infection_rates))
        self.infection_rates = self.r0 * self.infection_rates / self.infection_rates.sum()
        self.days = len(self.infection_rates)
        self.symptoms = np.array(symptoms or list(self.symptoms))
    
    def __init__(self):
        for id, var in variables.items():
            setattr(self, id, var.default)
        self.set_rates()
    
    def suppress(self):
        "Returns the daily effective infection rates, under current variable values."
        effective_symptoms = self.symptoms / ((100.0 - self.symptoms.sum()) * (self.asymptomatic_inf / 100.0) + self.symptoms.sum())
        
        rest = self.days - len(self.symptoms) - self.testing_delay
        testing_suppression = 1 - (self.testing_rate / 100.0) * (self.isolation_effectivity / 100.0) * effective_symptoms.cumsum()
        overall_testing_suppression = np.concatenate([
            np.ones(self.testing_delay),
            testing_suppression,
            np.repeat(testing_suppression[-1], rest) if rest > 0 else [],
        ])[:len(self.infection_rates)]
        
        rest = self.days - (self.testing_delay + self.tracing_delay)
        tracing_suppression = 1 - effective_symptoms.sum() * (self.testing_rate / 100.0) * (self.tracing_rate / 100.0) * (self.isolation_effectivity / 100.0)
        overall_tracing_suppression = np.concatenate([
            np.ones(self.testing_delay + self.tracing_delay),
            np.repeat(tracing_suppression, rest) if rest > 0 else [],
        ])[:len(self.infection_rates)]
        
        return self.infection_rates * overall_testing_suppression * overall_tracing_suppression
    
    # This function can also be written as:
    #   np.max(np.abs(np.roots(np.concatenate([[1], -a]))))
    # since A is a transformed companion matrix
    def compute_growth(self, a):
        "Given the effective daily infection rates, return the asymptotic daily growth."
        A = np.concatenate([
            a.reshape(1, self.days),
            np.diag(np.ones(self.days))[:-1]
        ])
        return np.max(np.abs(np.linalg.eig(A)[0]))
    
    def get_r_and_growth(self):
        "Computes and returns R and daily growth under current variable values."
        effective_daily_infectiousness = self.suppress()
        growth = self.compute_growth(effective_daily_infectiousness)
        return np.sum(effective_daily_infectiousness), (growth - 1.0) * 100

    def iterate(self, id):
        "Iterates through all possible settings of variable id, and compute R and asymptotic daily growth. Returns pandas dataframe."
        data = []
        var = variables[id]
        for x in frange(var.min, var.max, var.step):
            if id == "r0":
                self.set_rates(x)
            else:
                setattr(self, id, x)
            d = {k: v.getter(self) for k, v in variables.items()}
            d["r"], d["perc"] = self.get_r_and_growth()
            data.append(d)
        return pd.DataFrame.from_records(data)

    def _transmit(self, x):
        suppressed = self.suppress()
        r = np.sum(suppressed)
        newly_infected = x @ suppressed
        return np.append([newly_infected], x[:-1]), r

    def simulate(self, initial_cases=[1.0], n=100):
        "Runs simulation of cases, under current variable values."
        x = np.append(initial_cases, np.zeros(self.days-len(initial_cases))).reshape((1, self.days))
        rs = [self.r0]
        for i in range(n):
            new, r = self._transmit(x[-1])
            x = np.concatenate((x, new.reshape((1, self.days))))
            rs.append(r)
        return x, rs
    