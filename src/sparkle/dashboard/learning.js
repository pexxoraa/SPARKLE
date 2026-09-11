/* Authored practice UI. All stored content stays in text nodes. */
(() => {
  const add = (parent,tag,value='') => { const e=document.createElement(tag);e.textContent=value;parent.appendChild(e);return e; };
  async function load(container,api) {
    container.replaceChildren();
    const notice=add(container,'p','Practice scores are not verified competence. Answer keys are never returned here.');
    const learner=add(container,'input');learner.placeholder='Learner identity, e.g. learner_one';learner.maxLength=64;
    const view=add(container,'div');
    const post=(operation,args)=>api('/api/learning',{method:'POST',body:JSON.stringify({operation,...args,approved:true})});
    const showAttempt = attempt => {
      view.replaceChildren();
      add(view,'strong',`${attempt.exam}: ${attempt.status}`);
      add(view,'p',`Attempt ${attempt.id}; deadline ${new Date(attempt.deadline*1000).toISOString()}`);
      if(attempt.result) {
        add(view,'p',`Score: ${attempt.result.score_percent === null ? 'inconclusive' : attempt.result.score_percent+'%'}; passed: ${attempt.result.passed}; ${attempt.result.validation_status}`);
        for(const check of attempt.result.checks) add(view,'p',`${check.question_id}: ${check.earned}/${check.possible}; ${check.correct === null ? 'manual review pending' : check.correct ? 'correct' : 'review needed'}`);
        return;
      }
      const inputs=[];
      for(const q of attempt.questions) {
        const label=add(view,'label',q.prompt);
        let input;
        if(q.kind==='choice') {
          input=add(label,'select');const blank=add(input,'option','Choose an answer');blank.value='';
          for(const option of q.options) {const e=add(input,'option',option);e.value=option;}
        } else {input=add(label,q.kind==='manual'?'textarea':'input');input.maxLength=4000;}
        input.value=attempt.answers[q.id] ?? '';inputs.push([q,input]);
      }
      const message=add(view,'p');let busy=false;const buttons=[];
      for(const [label,action] of [['Save answers','answer'],['Submit attempt','submit'],['Cancel attempt','cancel'],['Refresh status','refresh']]) {
        const button=add(view,'button',label);buttons.push(button);
        button.addEventListener('click',async()=>{
          if(busy)return;
          if(['submit','cancel'].includes(action) && !globalThis.confirm(label+'?'))return;
          busy=true;buttons.forEach(b=>b.disabled=true);
          try {
            if(action==='refresh')return showAttempt(await api('/api/learning?attempt='+encodeURIComponent(attempt.id)));
            const answers={};
            for(const [q,input] of inputs) if(input.value!=='') {
              const value=q.kind==='number'?Number(input.value):input.value;
              if(q.kind==='number'&&!Number.isFinite(value))throw Error('invalid numeric answer');
              answers[q.id]=value;
            }
            showAttempt(await post('act',{attempt_id:attempt.id,action,expected_revision:attempt.revision,...(action==='cancel'?{}:{answers})}));
          } catch (_) {message.textContent='Operation failed. Refresh current attempt state before retrying.';}
          finally {busy=false;buttons.forEach(b=>b.disabled=false);}
        });
      }
    };
    const {courses}=await api('/api/learning');
    for(const course of courses.filter(c=>!c.archived)) {
      const card=add(container,'div');card.className='card';add(card,'h3',course.title);add(card,'p',course.goal);
      const open=add(card,'button','Inspect curriculum');
      open.addEventListener('click',async()=>{
        open.disabled=true;
        try {
          const d=await api('/api/learning?course='+encodeURIComponent(course.name));view.replaceChildren();
          for(const topic of d.topics) {const details=add(view,'details');add(details,'summary',topic.title);add(details,'p',topic.lesson);}
          for(const exam of d.exams) {
            const start=add(view,'button','Start '+exam.title);
            start.addEventListener('click',async()=>{
              if(!/^[a-z][a-z0-9_-]{1,63}$/.test(learner.value)) {notice.textContent='Enter a valid learner identity first.';return;}
              start.disabled=true;
              try {showAttempt(await post('start',{course:course.name,exam:exam.id,learner:learner.value,expected_revision:d.revision}));}
              catch (_) {notice.textContent='Start refused. Inspect progress for an existing attempt or unmet prerequisites.';}
              finally {start.disabled=false;}
            });
          }
        } catch (_) {notice.textContent='Curriculum could not be loaded.';} finally {open.disabled=false;}
      });
      const progress=add(card,'button','Inspect progress / resume');
      progress.addEventListener('click',async()=>{
        progress.disabled=true;
        try {
          const p=await api('/api/learning?course='+encodeURIComponent(course.name)+'&learner='+encodeURIComponent(learner.value));view.replaceChildren();
          for(const topic of p.topics)add(view,'p',`${topic.topic}: ${topic.next_action}; prerequisite blockers: ${topic.blocked_by.join(', ')||'none'}`);
          for(const attempt of p.attempts) {
            const button=add(view,'button',`${attempt.exam}: ${attempt.overdue ? "deadline reached — open result" : attempt.status}`);
            button.addEventListener('click',async()=>{button.disabled=true;try{showAttempt(await api('/api/learning?attempt='+encodeURIComponent(attempt.id)));}catch(_){notice.textContent='Attempt could not be loaded.';}finally{button.disabled=false;}});
          }
        } catch (_) {notice.textContent='Progress could not be loaded. Check learner identity.';}finally{progress.disabled=false;}
      });
    }
    if(!courses.length)add(container,'p','No curriculum installed. Import an authored definition through the approved CLI or API workflow.');
  }
  globalThis.SparkleLearning={load};
})();
