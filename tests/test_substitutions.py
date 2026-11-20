from app.modules.m2_substitutions.graph import cyclic_meals
from app.modules.m2_substitutions.service import approve


def test_cycle_is_removed_from_approved_edges(dirty_result):  # TRAP-20
    result=dirty_result['substitutions']
    assert result['cycle_meals']==['循环乙','循环甲']
    assert result['reasons']['SUBSTITUTION_CYCLE']==3
    assert ('暖粥','米香粥') in {(row['requested'],row['spare']) for row in result['rows']}


def test_full_component_not_just_first_edge():
    assert cyclic_meals([('甲','乙'),('乙','丙'),('丙','甲'),('丁','丙')])=={
        value:['丙','乙','甲'] for value in ('甲','乙','丙')}


def test_self_edge_is_a_cycle():
    assert cyclic_meals([('米饭','米饭')])=={'米饭':['米饭']}


def test_duplicate_rule_keeps_original_source(dirty_result):
    result=dirty_result['substitutions']
    assert result['reasons']['SUBSTITUTION_DUPLICATE']==1 and result['rows'][0]['line']==1


def test_malformed_rule_is_isolated(clean):
    clean['substitutions'].append({'requested':'暖粥','spare':' '})
    result=approve(clean,{})
    assert result['reasons']=={'SUBSTITUTION_SCHEMA':1} and len(result['rows'])==4


def test_edges_are_directional(clean_result):  # TRAP-21
    result=clean_result['substitutions']
    pairs={(row['requested'],row['spare']) for row in result['rows']}
    assert ('家常荤','粗粮荤') in pairs and ('粗粮荤','家常荤') not in pairs
