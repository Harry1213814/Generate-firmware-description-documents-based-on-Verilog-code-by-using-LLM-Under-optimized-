# Generate-firmware-description-documents-based-on-Verilog-code-by-using-LLM-Under-optimized-
基于verilog代码和system verilog代码生成固件描述文档(自用，欠优化)
该项目纯纯自娱自乐，依旧存在很多问题：
# 项目实现：
该项目由Reflection+Plan-and-Solve框架实现将Verilog和systemVerilog项目转换成一个人类可读的固件描述文档。
（起因是项目甲方急要，但我自己又不想写，把文件一个一个上传给GPT又太麻烦，于是学着写了一个Agent实现这个功能。但本人只学了HelloAgent项目中Agent的经典范式，于是乎该项目完成的并不理想）
1. 该项目会首先依次阅读工程文件中的.v或.sv代码，并生成一个摘要文件.statement.json
2. 之后会评审该.statement.json是否全面（是否遗漏always块？assign块？代码索引是否正确？代码功能是否描述清晰等），该评审结果继续写入.statement.json中
3. 之后根据评审结果修改.statement.json文件。直到max_feedback_rounds定义的次数。
4. 之后根据.statement.json文件生成.statement_doc.json文件，该文件是docx文件的json映射，后续会利用该文件直接生成docx文件。
5. 之后评审.statement_doc.json文件，是否代码全面，功能清晰？将评审结果写入.doc_feedback.json文件。
6. 之后根据.doc_feedback.json文件和.statement_doc.json以及项目原码对.statement_doc.json进行修改，直到达到max_doc_feedback_rounds定义的次数。
7. 最后使用.statement_doc.json生成docx文件

总结：该项目一共有三个步骤：
  1.摘要json（.statement.json）生成环节
  (1) 根据原码生成摘要json（.statement.json）(涉及plan-and-solve两个环节)
  (2) 根据摘要json反馈建议(涉及plan-and-solve两个环节)
  (3) 根据建议修改摘要json(涉及plan-and-solve两个环节)
  (4) 重复步骤(2-3)直到max_feedback_rounds定义的次数。
  2.doc_json(.statement_doc.json)生成环节
  (1) 根据原码和摘要Json生成.statement_doc.json(涉及plan-and-solve两个环节)
  (2) 根据doc_json反馈建议(涉及plan-and-solve两个环节)
  (3) 根据建议修改doc_json(涉及plan-and-solve两个环节)
  (4) 重复步骤(2-3)直到max_feedback_rounds定义的次数。
  3. docx生成环节
  (1) 根据.statement_doc.json生成docx文件(涉及plan-and-solve两个环节)

  # 项目中包含的内容：
  1. Reflection框架
  2. Plan-and-Solve框架（被Reflection调用）
  3. 4个工具及其表述：wr_Json写摘要Json；rd_verilog读取Verilog代码；wr_doc_json，写doc-json；wr_doc_feedback_json写doc-json的反馈json；doc_json_to_docx将doc-json转化成docx文件（被Plan-and-Solve框架调用）、
  4. 14组提示词


  # 该项目依旧存在的问题：
  1. 虽然在生成摘要Json（.statement.json）的阶段，LLM的提示词进行了限制（每一次只上传一个.v文件）但在后续的doc_json中没有进行memory限制。导致生成的doc_json存在很多问题，尽管reflection环节可以查出这些问题，但效率很低。
  2. 本项目仅支持verilog，尚未对其他所有代码进行支持，原因是在摘要Json中设置了只能写.v文件。
  3. 执行器的跳转方式死板。当前项目中若执行器成功调用一个工具，则会跳转到下一个步骤，虽然在提示词中限制了每一个计划只能使用一个工具，但效率较低
  4. 由于写doc-json阶段没有进行memory限制，导致Token爆炸！本人使用24个项目文件的Json在Kimi-K2.5上共花费了80元才完成，代价过高。
  5. 虽然引用了令牌机制限制LLM调用的频率，但没有对LLM报错的响应。如遇到“服务器繁忙”等问题，会发生反复尝试的爆炸问题。
  6. 计划阶段十分死板，容易生成控计划。原因是没有在计划阶段就直接读取反馈阶段的建议。
  7. 没有对docx生成阶段进行reflection。原因是DOC文件不方便支持修改的功能，若每一次修改都需要重写，则Token太过爆炸！

# 未来优化的方向：
1. 修改LLM的响应机制：根据不同的报错信息调整策略，无响应怎么办？服务器繁忙怎么办？
2. 修改LLM的运行机制：在生成摘要Json的时候，每一次读取一个.v文件，这个过程完全可以并发，提高代码效率。
3. 实现摘要json生成阶段与doc-json生成阶段的解耦。摘要json生成阶段需要读取.v原码，doc-json生成阶段则只依靠摘要Json进行功能归纳，不再需要读取.v代码中的具体含义。
4. 限制doc-json生成阶段的memory大小，如何合理的分配memory才能让doc-json既能获取当前模块的功能，又能获取当前模块上下游的接口信息和数据流，控制流流向与含义？
5. 如果AI写了一大段内容，然后在最后调用工具的时候写错了怎么办？AI下一次还需要重新生成这些内容，这会让Token增加一倍，如何避免这种Token浪费呢？
6. 如何让指定计划的阶段更加智能？先读取反馈的内容，再根据反馈的内容列出计划，这样在执行的阶段才不用动脑子。
