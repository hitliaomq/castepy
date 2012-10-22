from castepy.cell import Cell

def add_constraints(cell, filter):
  constraints = []
  i = 1
  for ion in cell.ions:
    if filter(ion):
      constraints.append("%d %s %d 1 0 0" % (i, ion.s, ion.i))
      constraints.append("%d %s %d 0 1 0" % (i+1, ion.s, ion.i))
      constraints.append("%d %s %d 0 0 1" % (i+2, ion.s, ion.i))
      i += 3

  cell.blocks['ionic_constraints'] = constraints

