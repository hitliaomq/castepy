import os, sys
import numpy
from cell import Cell
import bonds
from ion import Ion, Ions, least_mirror
from magres_constants import efg_to_Cq, K_to_J, val_to_Cq, largest_eval
import math

def write_vector(v):
  return " ".join([" " % x for x in v])

def write_matrix(m):
  return " ".join([" ".join(map(str,t)) for t in m])

def write_cell(cell):
  lines = [] 

  lines.append("lattice %s" % write_matrix(cell.lattice))

  for ion in cell.ions:
    p = ion.p
    if cell.ions_type == 'POSITIONS_FRAC':
      p = numpy.dot(cell.basis, p)
    lines.append("atom %s %d %s" % (ion.s, ion.i, write_vector(p)))

  for ion in cell.ions:
    if hasattr(ion, 'magres') and 'jc' in ion.magres:
      for (s, i), m in ion.magres['jc'].items():
        lines.append("jc %s %d %s %d %s" % (s, i, ion.s, ion.i, write_vector(m)))

  for ion in cell.ions:
    if hasattr(ion, 'magres') and 'ms' in ion.magres:
      lines.append("ms %s %d %s" % (ion.s, ion.i, write_vector(ion.magres['ms'])))
  
  for ion in cell.ions:
    if hasattr(ion, 'magres') and 'efg' in ion.magres:
      lines.append("efg %s %d %s" % (ion.s, ion.i, write_vector(ion.magres['efg'])))

  for bond in cell.ions.bonds:
    (s1, i1), (s2, i2), pop, r = bond
    p1 = cell.ions.get_species(s1, i1).p
    p2 = cell.ions.get_species(s2, i2).p

    d2, p2 = least_mirror(p2, p1,cell.basis, cell.lattice)

    if cell.ions_type == 'POSITIONS_FRAC':
      p1 = numpy.dot(cell.basis, p1)
      p2 = numpy.dot(cell.basis, p2)

    lines.append("bond %s %d %s %d %s %s" % (s1, i1, s2, i2, write_vector(p1), write_vector(p2)))  

  return "\n".join(lines)

def load_magres(magres_file):
  def sitensor33(d):
     return (data[0], int(data[1]), numpy.mat(numpy.reshape(map(float, data[2:]), (3,3))))
  
  def sisitensor33(d):
     return (data[0], int(data[1]), data[2], int(data[3]), numpy.mat(numpy.reshape(map(float, data[4:]), (3,3))))
  
  def atom(data):
    if len(data) == 5:
      return (data[0], int(data[1]), map(float, data[2:]))
    else:
      return (data[0], int(data[2]), map(float, data[3:]))

  proc = {'lattice': lambda data: numpy.reshape(map(float, data), (3,3)),
          'atom': atom,
          'ms': sitensor33,
          'efg': sitensor33, 'efg_local': sitensor33, 'efg_nonlocal': sitensor33,
          'isc': sisitensor33, 'isc_fc': sisitensor33, 'isc_spin': sisitensor33,
          'isc_orbital_p': sisitensor33, 'isc_orbital_d': sisitensor33,
          'label': lambda data: (data[0], int(data[1]), data[2]),}
  
  def clean(s):
    c = s.find('#')
    if c != -1:
      s = s[0:c]
    return s.strip()
 
  d = {}
  for line in magres_file.split('\n'):
    sline = clean(line).split()
    if len(sline) <= 1:
      continue

    tag = sline[0]
    data = sline[1:]

    if tag in proc:
      obj = proc[tag](data)
    else:
      continue
      obj = data

    if tag in d:
      d[tag].append(obj)
    else:
      d[tag] = [obj]

  return d

def load_into_dict(data):
  atoms = {}

  if "atom" not in data:
    return atoms

  for s,i,pos in data['atom']:
    atoms[(s,i)] = {}

  if "lattice" in data:
    atoms["lattice"] = data["lattice"]

  if 'efg' in data:
    for s,i,efg_tensor in data['efg']:
      atoms[(s,i)]['efg'] = val_to_Cq((efg_tensor + efg_tensor.H)/2.0, s)
      atoms[(s,i)]['Cq'] = largest_eval(atoms[(s,i)]['efg'])

  if 'efg_local' in data:
    for s,i,efg_tensor in data['efg_local']:
      atoms[(s,i)]['efg_local'] = val_to_Cq((efg_tensor + efg_tensor.H)/2.0, s)
      atoms[(s,i)]['Cq_local'] = largest_eval(atoms[(s,i)]['efg_local'])

  if 'efg_nonlocal' in data:
    for s,i,efg_tensor in data['efg_nonlocal']:
      atoms[(s,i)]['efg_nonlocal'] = val_to_Cq((efg_tensor + efg_tensor.H)/2.0, s)
      atoms[(s,i)]['Cq_nonlocal'] = largest_eval(atoms[(s,i)]['efg_nonlocal'])

  if 'ms' in data:
    for s,i,ms_tensor in data['ms']:
      atoms[(s,i)]['ms'] = (ms_tensor + ms_tensor.H)/2.0

  if 'isc' in data:
    for s1,i1,s2,i2,K_tensor in data['isc']:
      atoms[(s1,i1,s2,i2)] = {}
      atoms[(s1,i1,s2,i2)]['jc'] = K_to_J(K_tensor, s1, s2)

      if 'jc' not in atoms[(s1,i1)]:
        atoms[(s1,i1)]['jc'] = {}
      
      if 'jc' not in atoms[(s2,i2)]:
        atoms[(s2,i2)]['jc'] = {}

      atoms[(s1,i1)]['jc'][(s2,i2)] = atoms[(s1,i1,s2,i2)]['jc']
      atoms[(s2,i2)]['jc'][(s1,i1)] = atoms[(s1,i1,s2,i2)]['jc']

  if 'label' in data:
    for s, i, label in data['label']:
      atoms[(s,i)].site = label

  return atoms 

def load_into_dict_new(data):
  atoms = {}

  if "atom" not in data:
    return atoms

  atoms['atoms'] = {}
  for s,i,pos in data['atom']:
    atoms['atoms'][(s,i)] = pos

  if "lattice" in data:
    atoms["lattice"] = data["lattice"]

  #if 'efg' in data:
  #  atoms["efg"] = {}
  #  for s,i,efg_tensor in data['efg']:
  #    efg = val_to_Cq((efg_tensor + efg_tensor.H)/2.0, s)
#
#      Cq = largest_eval(efg)
#
#      atoms["efg"][(s,i)] = {'efg': efg,
#                             'Cq': Cq,}

  if 'ms' in data:
    atoms['ms'] = {}
    for s,i,ms_tensor in data['ms']:
      atoms['ms'][(s,i)] = (ms_tensor + ms_tensor.H)/2.0

  if 'isc' in data:
    atoms['jc'] = {}
    atoms['jc_iso'] = {}

    for s1, i1, s2, i2, K_tensor in data['isc']:
      if (s1,i1) not in atoms['jc']:
        atoms['jc'][(s1,i1)] = {}
        atoms['jc_iso'][(s1,i1)] = {}
      
      atoms['jc'][(s1,i1)][(s2,i2)] = K_to_J(K_tensor, s1, s2)
      atoms['jc_iso'][(s1,i1)][(s2,i2)] = numpy.trace(atoms['jc'][(s1,i1)][(s2,i2)])/3.0

  if 'label' in data:
    atoms['label'] = {}
    for s, i, label in data['label']:
      atoms['label'][(s,i)] = label

  return atoms

def load_into_ions(data):
  if len(data['lattice']) > 1:
    raise Exception("Too many lattice definitions.")

  ions = Ions()
  ions.lattice = data['lattice'][0]
  ions.basis = [[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]]
  for s, i, p in data['atom']:
    ion = Ion(s, p)
    ions.add(ion)

    if not hasattr(ion, 'magres'):
      ion.magres = {}
  
  if 'jc' in data:
    for s1, i1, s2, i2, m in data['jc']:
      ion = ions.get_species(s2, i2)

      if 'jc' not in ion.magres:
        ion.magres['jc'] = {}
      ion.magres['jc'][(s1, i1)] = m
   
  if 'efg' in data:
    for s, i, m in data['efg']:
      ion = ions.get_species(s, i)
      if 'efg' not in ion.magres:
        ion.magres['efg'] = {}
      ion.magres['efg'][(s1, i1)] = m

  if 'ms' in data:
    for s, i, m in data['ms']:
      ion = ions.get_species(s, i)

      if 'ms' not in ion.magres:
        ion.magres['ms'] = {}
      ion.magres['ms'] = m

  return ions

if __name__ == "__main__":
  if sys.argv[1] == 'load':
    magres_data = load_magres(open(sys.argv[2]).read())
    ions = load_into_ions(magres_data)

    for ion in ions: 
      if hasattr(ion, 'magres') and 'ms' in ion.magres:
        print ion.s, ion.i, ion.p, numpy.trace(numpy.reshape(ion.magres['ms'],(3,3)))/3.0
      if hasattr(ion, 'magres') and 'efg' in ion.magres:
        print ion.s, ion.i, ion.p, numpy.trace(numpy.reshape(ion.magres['efg'],(3,3)))/3.0
      if hasattr(ion, 'magres') and 'jc' in ion.magres:
        jc_tensor = ion.magres['jc'].items()[0][1]
        print ion.s, ion.i, jc_tensor

  elif sys.argv[1] == 'dump':
    from calc import CastepCalc
    
    dir, file = os.path.split(sys.argv[2])
    name, _ = os.path.splitext(file)
    
    calc = CastepCalc(dir, name)
    
    print >>sys.stderr, "Loading cell file"
    calc.load()
    c = calc.cell

    print write_cell(c)
