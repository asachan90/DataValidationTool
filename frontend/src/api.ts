import axios from 'axios'
import type {Execution, Pipeline} from './types'
export const api=axios.create({baseURL:'/api'})
export const listPipelines=()=>api.get<Pipeline[]>('/pipelines').then(r=>r.data)
export const createPipeline=(data:Partial<Pipeline>)=>api.post<Pipeline>('/pipelines',data).then(r=>r.data)
export const savePipeline=(p:Pipeline)=>api.put<Pipeline>(`/pipelines/${p.id}`,p).then(r=>r.data)
export const runPipeline=(id:string)=>api.post<Execution>(`/pipelines/${id}/run`).then(r=>r.data)
export const runToNode=(id:string,nodeId:string)=>api.post<Execution>(`/pipelines/${id}/run-to/${nodeId}`).then(r=>r.data)
