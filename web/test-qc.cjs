'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const qc = require('./qc.js');

const stats = qc.parseStats('level,mean,sd\nA,100,5\nB,200,10\n');
function evalRows(rows) { return qc.evaluate(qc.parseObservations('run,level,value\n' + rows.join('\n')),stats); }
function rules(row) { return row.violations.map(v => v.rule); }

test('normal points pass', () => assert.equal(evalRows(['1,A,100','1,B,200'])[0].verdict,'PASS'));
test('1-2s warning only', () => assert.equal(evalRows(['1,A,111'])[0].verdict,'WARNING'));
test('1-3s rejection', () => assert.ok(rules(evalRows(['1,A,116'])[0]).includes('1-3s')));
test('2-2s within-run same direction', () => assert.ok(rules(evalRows(['1,A,112','1,B,222'])[0]).includes('2-2s')));
test('2-2s across runs', () => assert.ok(rules(evalRows(['1,A,112','2,A,112'])[1]).includes('2-2s')));
test('R-4s opposite 2SD limits', () => assert.ok(rules(evalRows(['1,A,112','1,B,178'])[0]).includes('R-4s')));
test('R-4s not span-only', () => assert.ok(!rules(evalRows(['1,A,116','1,B,189'])[0]).includes('R-4s')));
test('4-1s', () => assert.ok(rules(evalRows(['1,A,106','2,A,106','3,A,106','4,A,106'])[3]).includes('4-1s')));
test('10x', () => {
  const rows = Array.from({length:10},(_,i)=>(i+1)+',A,101');
  assert.ok(rules(evalRows(rows)[9]).includes('10x'));
});
test('missing control level interrupts sequential history', () => {
  const r=evalRows(['1,A,112','2,B,200','3,A,112']);
  assert.equal(r[2].verdict,'WARNING');
});
test('CSV quotes and embedded commas',()=>{
  assert.equal(qc.parseObservations('run,level,value\n1,"A, weird",1')[0].level,'A, weird');
});
test('duplicate measurements rejected',()=>{
  assert.throws(()=>evalRows(['1,A,100','1,A,101']),/Duplicate/);
});
test('nonfinite values and invalid stats rejected',()=>{
  assert.throws(()=>qc.parseObservations('run,level,value\n1,A,NaN'),/finite/);
  assert.throws(()=>qc.parseStats('level,mean,sd\nA,100,0'),/positive/);
});
test('CSV formula payload is parsed as data not executed',()=>{
  const rows=qc.parseObservations('run,level,value\n1,"=HYPERLINK(""bad"")",12');
  assert.equal(rows[0].level,'=HYPERLINK("bad")');
});
